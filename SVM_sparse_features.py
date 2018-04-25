from __future__ import print_function

import logging
import numpy as np
from optparse import OptionParser
import sys
from time import time
import matplotlib.pyplot as plt

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.feature_selection import SelectFromModel
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.linear_model import RidgeClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.linear_model import SGDClassifier
from sklearn.linear_model import Perceptron
from sklearn.linear_model import PassiveAggressiveClassifier
from sklearn.naive_bayes import BernoulliNB, MultinomialNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neighbors import NearestCentroid
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.extmath import density
from sklearn import metrics



import csv, nltk
from nltk import word_tokenize



f = open("API_Train.csv", 'rU');
reader = csv.reader(f, delimiter=" ", quotechar='|')

main_corpus = []
main_corpus_target = []

my_categories = ['benign', 'malware']

# feeding corpus the testing data

print("Loading system call database for categories:")
print(my_categories if my_categories else "all")

aggregate = ""
count = 0
for line in reader:
  for field in line:
    if field[:1] != '0' and field[:1] != '1':
        aggregate += " "+field
    else:
        main_corpus.append(aggregate)
        if field[:1] == '0':
            count+=1
        main_corpus_target.append(int(field[:1]))
        aggregate = ""

print("Data loaded.")
print(count)


def size_mb(docs):
    return sum(len(s.encode('utf-8')) for s in docs) / 1e6

train_corpus = main_corpus[:(9*len(main_corpus)//10)]
train_corpus_target = main_corpus_target[:(9*len(main_corpus)//10)]
test_corpus = main_corpus[(len(main_corpus)-(len(main_corpus)//10)):]
test_corpus_target = main_corpus_target[(len(main_corpus)-len(main_corpus)//10):]

# size of datasets
train_corpus_size_mb = size_mb(train_corpus)
test_corpus_size_mb = size_mb(test_corpus)


print("%d documents - %0.3fMB (training set)" % (
    len(train_corpus_target), train_corpus_size_mb))
print("%d documents - %0.3fMB (test set)" % (
    len(test_corpus_target), test_corpus_size_mb))
print("%d categories" % len(my_categories))
print()


print("Extracting features from the training data using a sparse vectorizer...")
t0 = time()
# if opts.use_hashing:
#     vectorizer = HashingVectorizer(stop_words='english', alternate_sign=False,
#                                    n_features=opts.n_features)
#     X_train = vectorizer.transform(train_corpus)
# else:

vectorizer = TfidfVectorizer(ngram_range=(5, 5), min_df=1, use_idf=True, smooth_idf=True) ##############
analyze = vectorizer.build_analyzer()
print(analyze(test_corpus[1]))
X_train = vectorizer.fit_transform(train_corpus)



duration = time() - t0
print("done in %fs at %0.3fMB/s" % (duration, train_corpus_size_mb / duration))
print("n_samples: %d, n_features: %d" % X_train.shape)
print()

print("Extracting features from the test data using the same vectorizer...")
t0 = time()
X_test = vectorizer.transform(test_corpus)
duration = time() - t0
print("done in %fs at %0.3fMB/s" % (duration, test_corpus_size_mb / duration))
print("n_samples: %d, n_features: %d" % X_test.shape)
print()


def benchmark(clf):
    print('_'*60)
    print("Training: ")
    print(clf)
    t0 = time()
    clf.fit(X_train, train_corpus_target)
    train_time = time() - t0
    print("train time: %0.3fs" % train_time)

    t0 = time()
    pred = clf.predict(X_test)
    test_time = time() - t0
    print("test time: %0.3fs" % test_time)

    score = metrics.accuracy_score(test_corpus_target, pred)
    print("accuracy: %0.3f" % score)

    if hasattr(clf, 'coef_'):
        print("dimensionality: %d" % clf.coef_.shape[1])
        print("density: %f" % density(clf.coef_))
        print()
    print(metrics.classification_report(test_corpus_target, pred,target_names=my_categories))
    print()
    clf_descr = str(clf).split('(')[0]

    print("Predicted values: ")
    print(pred.tolist());
    print()
    print("Real values:")
    print(test_corpus_target)
    print()
    mCount = 0
    for i in test_corpus_target:
        if i == 1:
            mCount+=1
    print("Proportion of malicious trace:")
    print(mCount/len(test_corpus_target))

    return clf_descr, score, train_time, test_time

results = []
for clf, name in (
        (RidgeClassifier(tol=1e-2, solver="lsqr"), "Ridge Classifier"),
        (Perceptron(n_iter=50), "Perceptron"),
        (PassiveAggressiveClassifier(n_iter=50), "Passive-Aggressive"),
        (KNeighborsClassifier(n_neighbors=10), "kNN"),
        (RandomForestClassifier(n_estimators=100), "Random forest")):
    print('=' * 80)
    print(name)
    results.append(benchmark(clf))



for penalty in ["l2", "l1"]:
    print('=' * 80)
    print("%s penalty" % penalty.upper())
    # Train Liblinear model
    results.append(benchmark(LinearSVC(penalty=penalty, dual=False,
                                       tol=1e-3)))

    # Train SGD model
    results.append(benchmark(SGDClassifier(alpha=.0001, n_iter=50,
                                           penalty=penalty)))

# Train SGD with Elastic Net penalty
print('=' * 80)
print("Elastic-Net penalty")
results.append(benchmark(SGDClassifier(alpha=.0001, n_iter=50,
                                       penalty="elasticnet")))

# Train NearestCentroid without threshold
print('=' * 80)
print("NearestCentroid (aka Rocchio classifier)")
results.append(benchmark(NearestCentroid()))

# Train sparse Naive Bayes classifiers
print('=' * 80)
print("Naive Bayes")
results.append(benchmark(MultinomialNB(alpha=.01)))
results.append(benchmark(BernoulliNB(alpha=.01)))

print('=' * 80)
print("LinearSVC with L1-based feature selection")
# The smaller C, the stronger the regularization.
# The more regularization, the more sparsity.
results.append(benchmark(Pipeline([
  ('feature_selection', SelectFromModel(LinearSVC(penalty="l1", dual=False,
                                                  tol=1e-3))),
  ('classification', LinearSVC(penalty="l2"))])))


# plotting results

indices = np.arange(len(results))

results = [[x[i] for x in results] for i in range(4)]

clf_names, score, training_time, test_time = results
training_time = np.array(training_time) / np.max(training_time)
test_time = np.array(test_time) / np.max(test_time)

plt.figure(figsize=(12, 8))
plt.title("Score")
plt.barh(indices, score, .2, label="score", color='navy')
plt.barh(indices + .3, training_time, .2, label="training time",
         color='c')
plt.barh(indices + .6, test_time, .2, label="test time", color='darkorange')
plt.yticks(())
plt.legend(loc='best')
plt.subplots_adjust(left=.25)
plt.subplots_adjust(top=.95)
plt.subplots_adjust(bottom=.05)

for i, c in zip(indices, clf_names):
    plt.text(-.3, i, c)

plt.show()
