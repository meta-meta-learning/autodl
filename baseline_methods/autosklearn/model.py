# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Modified by: Zhengying Liu, Isabelle Guyon

"""An example of code submission for the AutoDL challenge.

It implements 3 compulsory methods: __init__, train, and test.
model.py follows the template of the abstract class algorithm.py found
in folder AutoDL_ingestion_program/.

To create a valid submission, zip model.py together with an empty
file called metadata (this just indicates your submission is a code submission
and has nothing to do with the dataset metadata.
"""

import tensorflow as tf
import os

# Import the challenge algorithm (model) API from algorithm.py
import algorithm

# Utility packages
import time
import datetime
import numpy as np
np.random.seed(42)
from autosklearn.classification import AutoSklearnClassifier

class Model(algorithm.Algorithm):
  """Construct CNN for classification."""

  def __init__(self, metadata):
    super(Model, self).__init__(metadata)

    # Get dataset name.
    self.dataset_name = self.metadata_.get_dataset_name()\
                          .split('/')[-2].split('.')[0]

    # Data in numpy.ndarray
    self.X_train = None
    self.Y_train = None
    self.X_test = None

    # Attributes for managing time budget
    # Cumulated number of training steps
    self.birthday = time.time()
    self.total_train_time = 0
    self.total_test_time = 0
    self.cumulated_num_tests = 0
    self.estimated_time_test = None
    self.train_time_for_next_run = 20
    self.done_training = False

  def train(self, dataset, remaining_time_budget=None):
    """Train this algorithm on the tensorflow |dataset|.

    This method will be called REPEATEDLY during the whole training/predicting
    process. So your `train` method should be able to handle repeated calls and
    hopefully improve your model performance after each call.

    Args:
      dataset: a `tf.data.Dataset` object. Each example is of the form
            (matrix_bundle_0, matrix_bundle_1, ..., matrix_bundle_(N-1), labels)
          where each matrix bundle is a tf.Tensor of shape
            (batch_size, sequence_size, row_count, col_count)
          with default `batch_size`=30 (if you wish you can unbatch and have any
          batch size you want). `labels` is a tf.Tensor of shape
            (batch_size, output_dim)
          The variable `output_dim` represents number of classes of this
          multilabel classification task. For the first version of AutoDL
          challenge, the number of bundles `N` will be set to 1.

      remaining_time_budget: time remaining to execute train(). The method
          should keep track of its execution time to avoid exceeding its time
          budget. If remaining_time_budget is None, no time budget is imposed.
    """
    if self.done_training:
      return

    # Transform data to numpy.ndarray if not done yet
    if not self.X_train or not self.Y_train:
      # Turn `features` in the tensor tuples (matrix_bundle_0,...,matrix_bundle_(N-1), labels)
      # to a dict. This example model only uses the first matrix bundle
      # (i.e. matrix_bundle_0) (see the documentation of this train() function above for the description of each example)
      dataset = dataset.map(lambda *x: ({'x': x[0]}, x[-1]))
      iterator = dataset.make_one_shot_iterator()
      next_element = iterator.get_next()
      counter = 0
      X_train = []
      Y_train = []
      with tf.Session() as sess:
        while True:
          try:
            features, labels = sess.run(next_element)
            X_train.append(features.flatten())
            Y_train.append(labels.flatten())
            counter += 1
            if counter % 1000 == 0:
              print(counter)
          except tf.errors.OutOfRangeError:
            print("The End.", counter)
            break
      self.X_train = np.array(X_train)
      self.Y_train = np.array(Y_train)

    if not remaining_time_budget: # This is never true in the competition anyway
      remaining_time_budget = 1200 # if no time limit is given, set to 20min

    train_time = min(self.train_time_for_next_run, remaining_time_budget - self.estimated_time_test - 10)

    train_start = time.time()
    # Start training

    train_end = time.time()
    # Update for time budget managing
    train_duration = train_end - train_start
    self.total_train_time += train_duration
    self.train_time_for_next_run *= 2

  def test(self, dataset, remaining_time_budget=None):
    """Test this algorithm on the tensorflow |dataset|.

    Args:
      Same as that of `train` method, except that the `labels` will be empty.
    Returns:
      predictions: A `numpy.ndarray` matrix of shape (sample_count, output_dim).
          here `sample_count` is the number of examples in this dataset as test
          set and `output_dim` is the number of labels to be predicted. The
          values should be binary or in the interval [0,1].
    """
    if self.done_training:
      return None

    # Transform data to numpy.ndarray if not done yet
    if not self.X_test:
      # Turn `features` in the tensor tuples (matrix_bundle_0,...,matrix_bundle_(N-1), labels)
      # to a dict. This example model only uses the first matrix bundle
      # (i.e. matrix_bundle_0) (see the documentation of this train() function above for the description of each example)
      dataset = dataset.map(lambda *x: ({'x': x[0]}, x[-1]))
      iterator = dataset.make_one_shot_iterator()
      next_element = iterator.get_next()
      counter = 0
      X_test = []
      with tf.Session() as sess:
        while True:
          try:
            features, labels = sess.run(next_element)
            X_test.append(features.flatten())
            counter += 1
            if counter % 1000 == 0:
              print(counter)
          except tf.errors.OutOfRangeError:
            print("The End.", counter)
            break
      self.X_test = np.array(X_test)

    # The following snippet of code intends to do:
    # 0. Use the function self.choose_to_stop_early() to decide if stop the whole
    #    train/predict process for next call
    # 1. If there is time budget limit, and some testing has already been done,
    #    but not enough remaining time for testing, then return None to stop
    # 2. Otherwise: make predictions normally, and update some
    #    variables for time managing
    if self.choose_to_stop_early():
      print_log("Oops! Choose to stop early for next call!")
      self.done_training = True
    test_begin = time.time()
    if remaining_time_budget and self.estimated_time_test and\
        self.estimated_time_test > remaining_time_budget:
      print_log("Not enough time for test. " +\
            "Estimated time for test: {:.2e}, ".format(self.estimated_time_test) +\
            "But remaining time budget is: {:.2f}. ".format(remaining_time_budget) +\
            "Stop train/predict process by returning None.")
      return None

    msg_est = ""
    if self.estimated_time_test:
      msg_est = "estimated time: {:.2e} sec.".format(self.estimated_time_test)
    print_log("Begin testing...", msg_est)
    test_results = self.classifier.predict(input_fn=test_input_fn)
    predictions = [x['probabilities'] for x in test_results]
    predictions = np.array(predictions)
    test_end = time.time()
    test_duration = test_end - test_begin
    self.total_test_time += test_duration
    self.cumulated_num_tests += 1
    self.estimated_time_test = self.total_test_time / self.cumulated_num_tests
    print_log("[+] Successfully made one prediction. {:.2f} sec used. ".format(test_duration) +\
          "Total time used for testing: {:.2f} sec. ".format(self.total_test_time) +\
          "Current estimated time for test: {:.2e} sec.".format(self.estimated_time_test))
    return predictions

  ##############################################################################
  #### Above 3 methods (__init__, train, test) should always be implemented ####
  ##############################################################################

  # Model functions that contain info on neural network architectures
  # Several model functions are to be implemented, for different domains
  def image_model_fn(self, features, labels, mode):
    """Medium CNN model for image datasets."""
    col_count, row_count = self.metadata_.get_matrix_size(0)
    sequence_size = self.metadata_.get_sequence_size()
    output_dim = self.metadata_.get_output_size()

    # Input Layer
    input_layer = features["x"]
    # Transpose X to 4-D tensor: [batch_size, row_count, col_count, sequence_size]
    # Normally the last axis should be channels instead of time axis, but they
    # are both equal to 1 for images
    hidden_layer = tf.transpose(input_layer, [0, 2, 3, 1])
    # At begining number of filters = 32
    num_filters = 32
    while True:
      hidden_layer = tf.layers.conv2d(
          inputs=hidden_layer,
          filters=num_filters,
          kernel_size=[3, 3],
          strides=(1, 1),
          padding="same",
          activation=tf.nn.relu)
      hidden_layer = tf.layers.max_pooling2d(inputs=hidden_layer, pool_size=[2, 2], strides=2)
      num_rows = hidden_layer.shape[1]
      num_columns = hidden_layer.shape[2]
      num_filters *= 2 # Double number of filters each time
      if num_rows == 1 or num_columns == 1:
        break
    hidden_layer = tf.layers.flatten(hidden_layer)
    hidden_layer = tf.layers.dense(inputs=hidden_layer, units=1024, activation=tf.nn.relu)
    hidden_layer = tf.layers.dropout(
        inputs=hidden_layer, rate=0.5, training=mode == tf.estimator.ModeKeys.TRAIN)
    logits = tf.layers.dense(inputs=hidden_layer, units=output_dim)
    sigmoid_tensor = tf.nn.sigmoid(logits, name="sigmoid_tensor")

    predictions = {
        # Generate predictions (for PREDICT and EVAL mode)
        "classes": tf.argmax(input=logits, axis=1),
        # Add `sigmoid_tensor` to the graph. It is used for PREDICT and by the
        # `logging_hook`.
        "probabilities": sigmoid_tensor
    }
    if mode == tf.estimator.ModeKeys.PREDICT:
      return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

    # Calculate Loss (for both TRAIN and EVAL modes)
    # For multi-label classification, a correct loss is sigmoid cross entropy
    loss = sigmoid_cross_entropy_with_logits(labels=labels, logits=logits)

    # Configure the Training Op (for TRAIN mode)
    if mode == tf.estimator.ModeKeys.TRAIN:
      optimizer = tf.train.AdamOptimizer()
      train_op = optimizer.minimize(
          loss=loss,
          global_step=tf.train.get_global_step())
      return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)

    # Add evaluation metrics (for EVAL mode)
    eval_metric_ops = {
        "accuracy": tf.metrics.accuracy(
            labels=labels, predictions=predictions["classes"])}
    return tf.estimator.EstimatorSpec(
        mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)

  def video_model_fn(self, features, labels, mode):
    """Model function for video dataset.

    Sum over time axis and then use dense neural network. Here this model is
    applied to video and text, for efficiency.
    """

    col_count, row_count = self.metadata_.get_matrix_size(0)
    sequence_size = self.metadata_.get_sequence_size()
    output_dim = self.metadata_.get_output_size()

    # Input Layer
    input_layer = features["x"]
    # Sum over time axis
    hidden_layer = tf.reduce_sum(features['x'], axis=1, keepdims=True)
    hidden_layer = tf.layers.flatten(hidden_layer)
    logits = tf.layers.dense(inputs=hidden_layer, units=output_dim)
    sigmoid_tensor = tf.nn.sigmoid(logits, name="sigmoid_tensor")

    predictions = {
      # Generate predictions (for PREDICT and EVAL mode)
      "classes": tf.argmax(input=logits, axis=1),
      # "classes": binary_predictions,
      # Add `sigmoid_tensor` to the graph. It is used for PREDICT and by the
      # `logging_hook`.
      "probabilities": sigmoid_tensor
    }
    if mode == tf.estimator.ModeKeys.PREDICT:
      return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

    # Calculate Loss (for both TRAIN and EVAL modes)
    # For multi-label classification, a correct loss is sigmoid cross entropy
    loss = sigmoid_cross_entropy_with_logits(labels=labels, logits=logits)

    # Configure the Training Op (for TRAIN mode)
    if mode == tf.estimator.ModeKeys.TRAIN:
      optimizer = tf.train.AdamOptimizer()
      train_op = optimizer.minimize(
          loss=loss,
          global_step=tf.train.get_global_step())
      return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)

    # Add evaluation metrics (for EVAL mode)
    assert mode == tf.estimator.ModeKeys.EVAL
    eval_metric_ops = {
        "accuracy": tf.metrics.accuracy(
            labels=labels, predictions=predictions["classes"])}
    return tf.estimator.EstimatorSpec(
        mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)

  def model_fn(self, features, labels, mode):
    """Dense neural network with 0 hidden layer.

    Flatten then dense. Can be applied to any task. Here we apply it to speech
    and tabular data.
    """
    col_count, row_count = self.metadata_.get_matrix_size(0)
    sequence_size = self.metadata_.get_sequence_size()
    output_dim = self.metadata_.get_output_size()

    # Construct a neural network with 0 hidden layer
    input_layer = tf.reshape(features["x"],
                             [-1, sequence_size*row_count*col_count])

    # Replace missing values by 0
    input_layer = tf.where(tf.is_nan(input_layer),
                           tf.zeros_like(input_layer), input_layer)

    input_layer = tf.layers.dense(inputs=input_layer, units=64, activation=tf.nn.relu)
    input_layer = tf.layers.dense(inputs=input_layer, units=128, activation=tf.nn.relu)
    input_layer = tf.layers.dropout(inputs=input_layer, rate=0.15, training=mode == tf.estimator.ModeKeys.TRAIN)
    input_layer = tf.layers.dense(inputs=input_layer, units=64, activation=tf.nn.relu)
    input_layer = tf.layers.dropout(inputs=input_layer, rate=0.15, training=mode == tf.estimator.ModeKeys.TRAIN)

    logits = tf.layers.dense(inputs=hidden_layer, units=output_dim)
    sigmoid_tensor = tf.nn.sigmoid(logits, name="sigmoid_tensor")

    predictions = {
      # Generate predictions (for PREDICT and EVAL mode)
      "classes": tf.argmax(input=logits, axis=1),
      # "classes": binary_predictions,
      # Add `sigmoid_tensor` to the graph. It is used for PREDICT and by the
      # `logging_hook`.
      "probabilities": sigmoid_tensor
    }
    if mode == tf.estimator.ModeKeys.PREDICT:
      return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

    # Calculate Loss (for both TRAIN and EVAL modes)
    # For multi-label classification, a correct loss is sigmoid cross entropy
    loss = sigmoid_cross_entropy_with_logits(labels=labels, logits=logits)

    # Configure the Training Op (for TRAIN mode)
    if mode == tf.estimator.ModeKeys.TRAIN:
      optimizer = tf.train.AdamOptimizer()
      train_op = optimizer.minimize(
          loss=loss,
          global_step=tf.train.get_global_step())
      return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)

    # Add evaluation metrics (for EVAL mode)
    assert mode == tf.estimator.ModeKeys.EVAL
    eval_metric_ops = {
        "accuracy": tf.metrics.accuracy(
            labels=labels, predictions=predictions["classes"])}
    return tf.estimator.EstimatorSpec(
        mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)

  # Some helper functions
  def infer_domain(self):
    col_count, row_count = self.metadata_.get_matrix_size(0)
    sequence_size = self.metadata_.get_sequence_size()
    output_dim = self.metadata_.get_output_size()
    if sequence_size > 1:
      if col_count == 1 and row_count == 1:
        return "speech"
      elif col_count > 1 and row_count > 1:
        return "video"
      else:
        return 'text'
    else:
      if col_count > 1 and row_count > 1:
        return 'image'
      else:
        return 'tabular'

  def age(self):
    return time.time() - self.birthday

  def choose_to_stop_early(self):
    """The criterion to stop further training (thus finish train/predict
    process).
    """
    # return self.cumulated_num_tests > 10 # Limit to make 10 predictions
    # return np.random.rand() < self.early_stop_proba
    batch_size = 30 # See ingestion program: D_train.init(batch_size=30, repeat=True)
    num_examples = self.metadata_.size()
    num_epochs = self.cumulated_num_steps * batch_size / num_examples
    return num_epochs > self.num_epochs_we_want_to_train # Train for certain number of epochs then stop

def print_log(*content):
  """Logging function. (could've also used `import logging`.)"""
  now = datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S")
  print("MODEL INFO: " + str(now)+ " ", end='')
  print(*content)

def sigmoid_cross_entropy_with_logits(labels=None, logits=None):
  """Re-implementation of this function:
    https://www.tensorflow.org/api_docs/python/tf/nn/sigmoid_cross_entropy_with_logits

  Let z = labels, x = logits, then return the sigmoid cross entropy
    max(x, 0) - x * z + log(1 + exp(-abs(x)))
  (Then sum over all classes.)
  """
  labels = tf.cast(labels, dtype=tf.float32)
  relu_logits = tf.nn.relu(logits)
  exp_logits = tf.math.exp(- tf.abs(logits))
  sigmoid_logits = tf.math.log(1 + exp_logits)
  element_wise_xent = relu_logits - labels * logits + sigmoid_logits
  return tf.reduce_sum(element_wise_xent)
