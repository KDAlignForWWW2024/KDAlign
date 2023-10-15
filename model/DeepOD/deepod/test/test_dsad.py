# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function

import os
import sys
import unittest

# noinspection PyProtectedMember
from numpy.testing import assert_equal
from sklearn.metrics import roc_auc_score
import torch

# temporary solution for relative imports in case pyod is not installed
# if deepod is installed, no need to use the following line
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deepod.models.tabular.dsad import DeepSAD
from deepod.models.time_series.dsad import DeepSADTS
from deepod.utils.data import generate_data
import numpy as np
from deepod.utils.utility import cal_metrics


class TestDSAD(unittest.TestCase):
    def setUp(self):
        self.n_train = 200
        self.n_test = 100
        self.contamination = 0.1
        self.roc_floor = 0.8
        self.ts_f1_floor = 0.0

        self.X_train, self.X_test, self.y_train, self.y_test = generate_data(
            n_train=self.n_train, n_test=self.n_test, n_features=10,
            contamination=self.contamination, random_state=42)

        # file = '../../data/38_thyroid.npz'
        # data = np.load(file, allow_pickle=True)
        # x, y = data['X'], data['y']
        # y = np.array(y, dtype=int)

        anom_id = np.where(self.y_train == 1)[0]
        known_anom_id = np.random.choice(anom_id, 10, replace=False)
        y_semi = np.zeros_like(self.y_train, dtype=int)
        y_semi[known_anom_id] = 1

        # # # ts data
        # train_file = 'data/omi-1/omi-1_train.csv'
        # test_file = 'data/omi-1/omi-1_test.csv'
        # train_df = pd.read_csv(train_file, index_col=0)
        # test_df = pd.read_csv(test_file, index_col=0)
        # y_train, y_test = train_df['label'].values, test_df['label'].values
        # train_df, test_df = train_df.drop('label', axis=1), test_df.drop('label', axis=1)
        # x_train = train_df.values
        # x_test = test_df.values

        # n = len(x_test)
        # self.Xts_train = np.vstack([x_train, x_test[:int(n * 0.5)]])
        # self.yts_train = np.hstack([y_train, y_test[:int(n * 0.5)]])
        # self.Xts_test = x_test[int(n * 0.5):]
        # self.yts_test = y_test[int(n * 0.5):]

        self.Xts_train = np.random.randn(1000, 19)
        self.yts_train = np.zeros(1000, dtype=int)
        self.yts_train[200:250] = 1
        self.Xts_test = self.Xts_train.copy()
        self.yts_test = self.yts_train.copy()

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.clf = DeepSAD(epochs=1, hidden_dims=20,
                           device=device,
                           random_state=42)
        self.clf.fit(self.X_train, y_semi)

        self.clf2 = DeepSADTS(stride=50, seq_len=100, epochs=20,
                              device=device, network='Transformer')
        self.clf2.fit(self.Xts_train, self.yts_train)

    def test_parameters(self):
        assert (hasattr(self.clf2, 'decision_scores_') and
                self.clf2.decision_scores_ is not None)
        assert (hasattr(self.clf2, 'labels_') and
                self.clf2.labels_ is not None)
        assert (hasattr(self.clf2, 'threshold_') and
                self.clf2.threshold_ is not None)

    def test_train_scores(self):
        assert_equal(len(self.clf2.decision_scores_), self.Xts_train.shape[0])
        assert_equal(len(self.clf.decision_scores_), self.X_train.shape[0])

    def test_prediction_scores(self):
        pred_scores = self.clf.decision_function(self.X_test)
        pred_scores2 = self.clf2.decision_function(self.Xts_test)

        # check score shapes
        assert_equal(pred_scores.shape[0], self.X_test.shape[0])
        assert_equal(pred_scores2.shape[0], self.Xts_test.shape[0])

        # check performance
        auc = roc_auc_score(self.y_test, pred_scores)
        assert (auc >= self.roc_floor), \
            f'auc {auc} does not reach minimum auc standard {self.roc_floor}'
        adj_eval_info = cal_metrics(self.yts_test, pred_scores2, pa=True)
        assert (adj_eval_info[2] >= self.ts_f1_floor), \
            f'pa_f1 {adj_eval_info[2]} does not reach minimum f1 standard {self.ts_f1_floor}'

    def test_prediction_labels(self):
        pred_labels = self.clf.predict(self.X_test)
        pred_labels2 = self.clf2.predict(self.Xts_test)
        assert_equal(pred_labels.shape, self.y_test.shape)
        assert_equal(pred_labels2.shape, self.yts_test.shape)

    # def test_prediction_proba(self):
    #     pred_proba = self.clf.predict_proba(self.X_test)
    #     assert (pred_proba.min() >= 0)
    #     assert (pred_proba.max() <= 1)
    #
    # def test_prediction_proba_linear(self):
    #     pred_proba = self.clf.predict_proba(self.X_test, method='linear')
    #     assert (pred_proba.min() >= 0)
    #     assert (pred_proba.max() <= 1)
    #
    # def test_prediction_proba_unify(self):
    #     pred_proba = self.clf.predict_proba(self.X_test, method='unify')
    #     assert (pred_proba.min() >= 0)
    #     assert (pred_proba.max() <= 1)
    #
    # def test_prediction_proba_parameter(self):
    #     with assert_raises(ValueError):
    #         self.clf.predict_proba(self.X_test, method='something')

    def test_prediction_labels_confidence(self):
        pred_labels, confidence = self.clf.predict(self.X_test,
                                                   return_confidence=True)
        assert_equal(pred_labels.shape, self.y_test.shape)
        assert_equal(confidence.shape, self.y_test.shape)
        assert (confidence.min() >= 0)
        assert (confidence.max() <= 1)

        pred_labels, confidence = self.clf2.predict(self.Xts_test,
                                                    return_confidence=True)
        assert_equal(pred_labels.shape, self.yts_test.shape)
        assert_equal(confidence.shape, self.yts_test.shape)
        assert (confidence.min() >= 0)
        assert (confidence.max() <= 1)

    # def test_prediction_proba_linear_confidence(self):
    #     pred_proba, confidence = self.clf.predict_proba(self.X_test,
    #                                                     method='linear',
    #                                                     return_confidence=True)
    #     assert (pred_proba.min() >= 0)
    #     assert (pred_proba.max() <= 1)
    #
    #     assert_equal(confidence.shape, self.y_test.shape)
    #     assert (confidence.min() >= 0)
    #     assert (confidence.max() <= 1)
    #
    # def test_fit_predict(self):
    #     pred_labels = self.clf.fit_predict(self.X_train)
    #     assert_equal(pred_labels.shape, self.y_train.shape)
    #
    # def test_fit_predict_score(self):
    #     self.clf.fit_predict_score(self.X_test, self.y_test)
    #     self.clf.fit_predict_score(self.X_test, self.y_test,
    #                                scoring='roc_auc_score')
    #     self.clf.fit_predict_score(self.X_test, self.y_test,
    #                                scoring='prc_n_score')
    #     with assert_raises(NotImplementedError):
    #         self.clf.fit_predict_score(self.X_test, self.y_test,
    #                                    scoring='something')
    #
    # def test_predict_rank(self):
    #     pred_socres = self.clf.decision_function(self.X_test)
    #     pred_ranks = self.clf._predict_rank(self.X_test)
    #
    #     # assert the order is reserved
    #     assert_allclose(rankdata(pred_ranks), rankdata(pred_socres), atol=3)
    #     assert_array_less(pred_ranks, self.X_train.shape[0] + 1)
    #     assert_array_less(-0.1, pred_ranks)
    #
    # def test_predict_rank_normalized(self):
    #     pred_socres = self.clf.decision_function(self.X_test)
    #     pred_ranks = self.clf._predict_rank(self.X_test, normalized=True)
    #
    #     # assert the order is reserved
    #     assert_allclose(rankdata(pred_ranks), rankdata(pred_socres), atol=3)
    #     assert_array_less(pred_ranks, 1.01)
    #     assert_array_less(-0.1, pred_ranks)

    # def test_plot(self):
    #     os, cutoff1, cutoff2 = self.clf.explain_outlier(ind=1)
    #     assert_array_less(0, os)

    # def test_model_clone(self):
    #     clone_clf = clone(self.clf)

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()