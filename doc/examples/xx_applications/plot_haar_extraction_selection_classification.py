"""
======================================================
Face classification using Haar-like feature descriptor
======================================================

Haar-like feature descriptors were successfully used to implement the first
real-time face detector [1]_. Inspired by this application, we propose an
example illustrating the extraction, selection, and classification of Haar-like
features to detect faces vs. non-faces.

Notes
-----

This example relies on scikit-learn to select and classify features.

References
----------

.. [1] Viola, Paul, and Michael J. Jones. "Robust real-time face
       detection." International journal of computer vision 57.2
       (2004): 137-154.
       http://www.merl.com/publications/docs/TR2004-043.pdf
       DOI: 10.1109/CVPR.2001.990517

"""
from __future__ import print_function

import numpy as np
import matplotlib.pyplot as plt

from dask import delayed, multiprocessing

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from skimage.data import lfw_subset
from skimage.transform import integral_image
from skimage.feature import haar_like_feature
from skimage.feature import haar_like_feature_coord
from skimage.feature import draw_haar_like_feature

###############################################################################
# The usual feature extraction scheme
###############################################################################
# The procedure to extract the Haar-like feature for an image is quite easy: a
# region of interest (ROI) is defined for which all possible feature will be
# extracted. The integral image of this ROI will be computed and all possible
# features will be computed.


@delayed
def extract_feature_image(img, feature_type, feature_coord=None):
    """Extract the haar feature for the current image"""
    ii = integral_image(img)
    return haar_like_feature(ii, 0, 0, ii.shape[0], ii.shape[1],
                             feature_type=feature_type,
                             feature_coord=feature_coord)


###############################################################################
# We will use a subset of the CBCL which is composed of 100 face images and 100
# non-face images. Each image has been resized to a ROI of 19 by 19 pixels. We
# will keep 75 images from each group to train a classifier and check which
# extracted features are the most salient, and use the remaining 25 from each
# class to check the performance of the classifier.

images = lfw_subset()
# For speed, only extract the two first types of features
feature_types = ['type-2-x', 'type-2-y']

# Build a computation graph using dask. This allows using multiple CPUs for
# the computation step
X = delayed(extract_feature_image(img, feature_types)
            for img in images)
# Compute the result using the "multiprocessing" dask backend
X = np.array(X.compute(get=multiprocessing.get))
y = np.array([1] * 100 + [0] * 100)
X_train, X_test, y_train, y_test = train_test_split(X, y, train_size=150,
                                                    random_state=0)

# Extract all possible features to be able to select the most salient.
feature_coord, feature_type = \
        haar_like_feature_coord(width=images.shape[2], height=images.shape[1],
                                feature_type=feature_types)

###############################################################################
# A random forest classifier can be trained in order to select the most salient
# features, specifically for face classification. The idea is to check which
# features are the most often used by the ensemble of trees. By using only
# the most salient features in subsequent steps, we can dramatically speed up
# computation, while retaining accuracy.

# Train a random forest classifier and check performance
clf = RandomForestClassifier(n_estimators=1000, max_depth=None,
                             max_features=100, n_jobs=-1, random_state=0)
clf.fit(X_train, y_train)

# Sort features in order of importance, plot six most significant
idx_sorted = np.argsort(clf.feature_importances_)[::-1]

fig, axes = plt.subplots(3, 2)
for idx, ax in enumerate(axes.ravel()):
    image = images[0]
    image = draw_haar_like_feature(image, 0, 0,
                                   images.shape[2],
                                   images.shape[1],
                                   [feature_coord[idx_sorted[idx]]])
    ax.imshow(image)
    ax.set_xticks([])
    ax.set_yticks([])

fig.suptitle('The most important features')

###############################################################################
# We can select the most important features by checking the cumulative sum of
# the feature importance index; below, we keep features representing 70% of the
# cumulative value which represent only 3% of the total number of features.

cdf_feature_importances = np.cumsum(clf.feature_importances_[idx_sorted[::-1]])
cdf_feature_importances /= np.max(cdf_feature_importances)
significant_feature = np.count_nonzero(cdf_feature_importances > 0.3)
print('There is {} features which are considered important.'.format(
    significant_feature))

# Select the most informative features
selected_feature_coord = feature_coord[idx_sorted[:significant_feature]]
selected_feature_type = feature_type[idx_sorted[:significant_feature]]
# Note: we could select those features from the
# original matrix X but we would like to emphasize the usage of `feature_coord`
# and `feature_type` to recompute a subset of desired features.

# Delay the computation and build the graph using dask
X = delayed(extract_feature_image(img, selected_feature_type,
                                  selected_feature_coord)
            for img in images)
# Compute the result using the multiprocessing backend
X = np.array(X.compute(get=multiprocessing.get))
y = np.array([1] * 100 + [0] * 100)
X_train, X_test, y_train, y_test = train_test_split(X, y, train_size=150,
                                                    random_state=0)

###############################################################################
# Once the feature are extracted, we can train and test the a new classifier.

clf.fit(X_train, y_train)
y_pred = clf.predict(X_test)
print(classification_report(y_test, y_pred))
plt.show()
