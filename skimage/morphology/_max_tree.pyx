"""_max_tree.pyx - building a max-tree from an image.

This is an implementation of the max-tree, which is a morphological
representation of the image. Many morphological operators can be built
from this representation, namely attribute openings and closings.

This file also contains implementations of max-tree based filters and
functions to characterize the tree components. 
"""

import numpy as np

from libc.stdlib cimport free, malloc, realloc
from scipy.constants.constants import point

cimport numpy as np
cimport cython

ctypedef np.float64_t DTYPE_FLOAT64_t
ctypedef np.int32_t DTYPE_INT32_t
ctypedef np.uint32_t DTYPE_UINT32_t
ctypedef np.uint64_t DTYPE_UINT64_t
ctypedef np.int64_t DTYPE_INT64_t
ctypedef np.uint8_t DTYPE_BOOL_t
ctypedef np.uint8_t DTYPE_UINT8_t

ctypedef fused dtype_t:
    np.uint8_t
    np.uint16_t
    np.uint32_t
    np.uint64_t
    np.int8_t
    np.int16_t
    np.int32_t
    np.int64_t
    np.float32_t
    np.float64_t

cdef inline DTYPE_UINT64_t uint64_max(DTYPE_UINT64_t a, DTYPE_UINT64_t b): return a if a >= b else b
cdef inline DTYPE_UINT64_t uint64_min(DTYPE_UINT64_t a, DTYPE_UINT64_t b): return a if a <= b else b


# recursive function to get the root of the current tree. Importantly, the
# function changes the tree (path compression), that reduces the complexity
# from O(n*n) to O(n*log(n)).
cdef DTYPE_INT64_t find_root(DTYPE_INT64_t[::1] parent, DTYPE_INT64_t index):
    if parent[index] != index:
        parent[index] = find_root(parent, parent[index])
    return parent[index]

# canonicalize generates a max-tree for which every node's
# parent is a canonical node. Namely, either the representative node of the
# same level or the representative node at the level below.
cdef void canonize(dtype_t[::1] image, DTYPE_INT64_t[::1] parent,
                   DTYPE_INT64_t[::1] sorted_indices):
    cdef DTYPE_INT64_t q = 0
    for p in sorted_indices:
        q = parent[p]
        if image[q] == image[parent[q]]:
            parent[p] = parent[q]
    return


# helper function: a list of offsets is transformed to a list of points,
# which are stored in a numpy array: rows correspond to different points,
# columns to the dimensions (typically 2 or 3, but there is no limitation).
cdef np.ndarray[DTYPE_INT32_t, ndim=2] offsets_to_points(DTYPE_INT32_t[::1] offsets, 
                                                         DTYPE_INT32_t[::1] shape):
    cdef DTYPE_INT32_t number_of_dimensions = len(shape)
    cdef DTYPE_INT32_t number_of_points = len(offsets)
    cdef np.ndarray[DTYPE_INT32_t, ndim=2] points = np.zeros((number_of_points, number_of_dimensions),
                                                             dtype=np.int32)
    cdef DTYPE_INT32_t neg_shift = - np.min(offsets)
    
    cdef DTYPE_INT32_t i, offset, curr_index, coord, 
 
    center_point = np.unravel_index(neg_shift, shape)    
        
    for i, offset in enumerate(offsets):
        current_point = np.unravel_index(offset + neg_shift, shape)
        for d in range(number_of_dimensions):
            points[i,d] = current_point[d] - center_point[d]
            
    return points


# checks whether a neighbor of a given pixel is inside the image plane.
# The pixel is given in form of an index of a raveled array, the offset
# is given as a list of coordinates. This function is relatively time-consuming
# and should only be applied to border-pixels (defined by mask).
cdef DTYPE_UINT8_t _is_valid_coordinate(DTYPE_INT64_t index,
                                        DTYPE_INT32_t[::1] coordinates,
                                        DTYPE_INT32_t[::1] shape):
    cdef DTYPE_INT64_t number_of_dimensions = len(shape)
    cdef DTYPE_INT64_t res_coord = 0
    cdef int i = 0
        
    p_coord = np.array(np.unravel_index(index, shape))
    
    # get the coordinates of the point from a 1D index 
    for i in range(number_of_dimensions):
        res_coord = p_coord[i] + coordinates[i]
                
        if res_coord < 0:
            return 0
        if res_coord >= shape[i]:
            return 0
        
    return 1


cpdef np.ndarray[DTYPE_FLOAT64_t, ndim=1] _compute_area(dtype_t[::1] image,
                                                        DTYPE_INT64_t[::1] parent,
                                                        DTYPE_INT64_t[::1] sorted_indices):
    cdef DTYPE_INT64_t p_root = sorted_indices[0]
    cdef DTYPE_INT64_t p, q
    cdef DTYPE_UINT64_t number_of_pixels = len(image)
    cdef np.ndarray[DTYPE_FLOAT64_t, ndim=1] area = np.ones(number_of_pixels,
                                                           dtype=np.float64)

    for p in sorted_indices[::-1]:
        if p == p_root:
            continue
        q = parent[p]
        area[q] = area[q] + area[p] 
    return area


cpdef void _direct_filter(dtype_t[::1] image,
                          dtype_t[::1] output,
                          DTYPE_INT64_t[::1] parent,
                          DTYPE_INT64_t[::1] sorted_indices,
                          DTYPE_FLOAT64_t[::1] attribute,
                          DTYPE_FLOAT64_t attribute_threshold
                          ):
    """Direct filtering. Produces an image in which for all possible thresholds, 
    each connected component has an attribute >= attribute_threshold.

    Parameters
    ----------

    image : array of arbitrary type
            The flattened image pixels.
    output : array of the same shape and type as image.
    parent : array of int
        Image of the same shape as the input image. The value
        at each pixel is the parent index of this pixel in the max-tree
        reprentation. 
    sorted_indices : array of int
        List of length = number of pixels. Each element
        corresponds to one pixel index in the image. It encodes the order
        of elements in the tree: a parent of a pixel always comes before
        the element itself. More formally: i < j implies that j cannot be
        the parent of i.
    attribute : array of float 
        Contains the attributes for the max-tree
    attribute_threshold : float
        The threshold to be applied to the attribute.
    """

    cdef DTYPE_INT64_t p_root = sorted_indices[0]
    cdef DTYPE_INT64_t p, q
    cdef DTYPE_UINT64_t number_of_pixels = len(image)

    if attribute[p_root] < attribute_threshold:
        output[p_root] = 0
    else:
        output[p_root] = image[p_root]

    for p in sorted_indices:
        if p == p_root:
            continue

        q = parent[p]

        # this means p is not canonical
        # in other words, it has a parent that has the
        # same image value. 
        if image[p] == image[q]:
            output[p] = output[q]
            continue

        if attribute[p] < attribute_threshold:
            # this corresponds to stopping
            # as the level of the lower parent 
            # is propagated to the current level
            output[p] = output[q]
        else:
            # here the image reconstruction continues.
            # The level is maintained (original value). 
            output[p] = image[p]

    return

cpdef void _cut_first_filter(dtype_t[::1] image,
                             dtype_t[::1] output,
                             DTYPE_INT64_t[::1] parent,
                             DTYPE_INT64_t[::1] sorted_indices,
                             DTYPE_FLOAT64_t[::1] attribute,
                             DTYPE_FLOAT64_t attribute_threshold
                             ):
    """Image filter using max-trees: starting from the root, the tree is pruned
    if the attribute of a component is smaller than the threshold. For increasing
    attributes, this is the same as _direct_filter, but for non-increasing attributes,
    the results are different (and more severe).

    Parameters
    ----------

    image : array of arbitrary type
            The flattened image pixels.
    output : array of the same shape and type as image.
    parent : array of int
        Image of the same shape as the input image. The value
        at each pixel is the parent index of this pixel in the max-tree
        reprentation. 
    sorted_indices : array of int
        List of length = number of pixels. Each element
        corresponds to one pixel index in the image. It encodes the order
        of elements in the tree: a parent of a pixel always comes before
        the element itself. More formally: i < j implies that j cannot be
        the parent of i.
    attribute : array of float 
        Contains the attributes for the max-tree
    attribute_threshold : float
        The threshold to be applied to the attribute.
    """

    cdef DTYPE_INT64_t p_root = sorted_indices[0]
    cdef DTYPE_INT64_t p, q
    cdef DTYPE_UINT64_t number_of_pixels = len(image)

    if attribute[p_root] < attribute_threshold:
        output[p_root] = 0
    else:
        output[p_root] = image[p_root]

    for p in sorted_indices:
        if p == p_root:
            continue

        q = parent[p]

        # in this case we propagate on the same level
        if image[p] == image[q]:
            output[p] = output[q]
            continue

        # here we jump in level
        if (attribute[p] < attribute_threshold) or (output[q] < image[q]):
            # in this case the stop criterion is fulfilled
            # or was fulfilled for a previous level.
            # the level of the last level is propagated.
            output[p] = output[q]
        else:
            # in this case the stop criterion is not fulfilled
            # and this level is reconstructed entirely (flooding continues)
            output[p] = image[p]

    return


cpdef void _build_max_tree(dtype_t[::1] image,
                           DTYPE_BOOL_t[::1] mask,
                           DTYPE_INT32_t[::1] structure,
                           DTYPE_INT32_t[::1] shape,
                           DTYPE_INT64_t[::1] parent,
                           DTYPE_INT64_t[::1] sorted_indices
                           ):
    """Builds a max-tree.

    Parameters
    ----------

    image : array of arbitrary type
            The flattened image pixels.
    mask : array of int
        An array of the same shape as `image` where each pixel contains a
        nonzero value if it is to be considered for the filtering.
        NOTE: it is *essential* that the border pixels (those
        with neighbors falling outside the volume) are all set to zero, or
        segfaults could occur.
    structure : array of int
        A list of coordinate offsets to compute the raveled coordinates of each
        neighbor from the raveled coordinates of the current pixel.
    parent : array of int
        First output: image of the same shape as the input image. The value
        at each pixel is the parent index of this pixel in the max-tree
        reprentation.
    tree_order : array of int
        Second output: list of length = number of pixels. Each element
        corresponds to one pixel index in the image. It encodes the order
        of elements in the tree: a parent of a pixel always comes before
        the element itself. More formally: i < j implies that j cannot be
        the parent of i.
    """
    cdef DTYPE_UINT64_t number_of_pixels = len(image)
    cdef DTYPE_UINT64_t number_of_dimensions = len(strides)

    cdef DTYPE_INT64_t i = 0
    cdef DTYPE_INT64_t p = 0
    cdef DTYPE_INT64_t root = 0
    cdef DTYPE_INT64_t index = 0

    cdef Py_ssize_t nneighbors = structure.shape[0]

    cdef DTYPE_INT64_t[::1] zpar = parent.copy()

    cdef np.ndarray[DTYPE_INT32_t, ndim=2] points = offsets_to_points(structure, shape)
    
    # initialization of the image parent.
    for i in range(number_of_pixels):
        parent[i] = -1
        zpar[i] = -1

    # traverse the array in reversed order
    for p in sorted_indices[::-1]:
        parent[p] = p
        zpar[p] = p
        
        for i in range(nneighbors):
            
            # get the flattened address of the neighbor
            index = p + structure[i]
            
            if not mask[p]:
                # in this case, p is at the border of the image.
                # there must be therefore some neighbor point which is not valid. 
                if not _is_valid_coordinate(p, points[i], shape):
                    # neighbor is not in the image. 
                    continue
            
            if parent[index] < 0:
                # in this case the parent is not yet set: we ignore
                continue

            root = find_root(zpar, index)

            if root != p:
                zpar[root] = p
                parent[root] = p

    # In a canonized max-tree, each parent is a canonical pixel,
    # i.e. for each connected component at a level l, all pixels point
    # to the same representative which in turn points to the representative
    # pixel at the next level.
    canonize(image, parent, sorted_indices)

    return
