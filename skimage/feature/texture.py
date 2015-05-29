"""
Methods to characterize image textures.
"""

import numpy as np
from .._shared.utils import assert_nD
from ._texture import _glcm_loop, _local_binary_pattern

from ..transform import integrate


def greycomatrix(image, distances, angles, levels=256, symmetric=False,
                 normed=False):
    """Calculate the grey-level co-occurrence matrix.

    A grey level co-occurrence matrix is a histogram of co-occurring
    greyscale values at a given offset over an image.

    Parameters
    ----------
    image : array_like of uint8
        Integer typed input image. The image will be cast to uint8, so
        the maximum value must be less than 256.
    distances : array_like
        List of pixel pair distance offsets.
    angles : array_like
        List of pixel pair angles in radians.
    levels : int, optional
        The input image should contain integers in [0, levels-1],
        where levels indicate the number of grey-levels counted
        (typically 256 for an 8-bit image). The maximum value is
        256.
    symmetric : bool, optional
        If True, the output matrix `P[:, :, d, theta]` is symmetric. This
        is accomplished by ignoring the order of value pairs, so both
        (i, j) and (j, i) are accumulated when (i, j) is encountered
        for a given offset. The default is False.
    normed : bool, optional
        If True, normalize each matrix `P[:, :, d, theta]` by dividing
        by the total number of accumulated co-occurrences for the given
        offset. The elements of the resulting matrix sum to 1. The
        default is False.

    Returns
    -------
    P : 4-D ndarray
        The grey-level co-occurrence histogram. The value
        `P[i,j,d,theta]` is the number of times that grey-level `j`
        occurs at a distance `d` and at an angle `theta` from
        grey-level `i`. If `normed` is `False`, the output is of
        type uint32, otherwise it is float64.

    References
    ----------
    .. [1] The GLCM Tutorial Home Page,
           http://www.fp.ucalgary.ca/mhallbey/tutorial.htm
    .. [2] Pattern Recognition Engineering, Morton Nadler & Eric P.
           Smith
    .. [3] Wikipedia, http://en.wikipedia.org/wiki/Co-occurrence_matrix


    Examples
    --------
    Compute 2 GLCMs: One for a 1-pixel offset to the right, and one
    for a 1-pixel offset upwards.

    >>> image = np.array([[0, 0, 1, 1],
    ...                   [0, 0, 1, 1],
    ...                   [0, 2, 2, 2],
    ...                   [2, 2, 3, 3]], dtype=np.uint8)
    >>> result = greycomatrix(image, [1], [0, np.pi/4, np.pi/2, 3*np.pi/4], levels=4)
    >>> result[:, :, 0, 0]
    array([[2, 2, 1, 0],
           [0, 2, 0, 0],
           [0, 0, 3, 1],
           [0, 0, 0, 1]], dtype=uint32)
    >>> result[:, :, 0, 1]
    array([[1, 1, 3, 0],
           [0, 1, 1, 0],
           [0, 0, 0, 2],
           [0, 0, 0, 0]], dtype=uint32)
    >>> result[:, :, 0, 2]
    array([[3, 0, 2, 0],
           [0, 2, 2, 0],
           [0, 0, 1, 2],
           [0, 0, 0, 0]], dtype=uint32)
    >>> result[:, :, 0, 3]
    array([[2, 0, 0, 0],
           [1, 1, 2, 0],
           [0, 0, 2, 1],
           [0, 0, 0, 0]], dtype=uint32)

    """
    assert_nD(image, 2)
    assert_nD(distances, 1, 'distances')
    assert_nD(angles, 1, 'angles')

    assert levels <= 256
    image = np.ascontiguousarray(image)
    assert image.min() >= 0
    assert image.max() < levels
    image = image.astype(np.uint8)
    distances = np.ascontiguousarray(distances, dtype=np.float64)
    angles = np.ascontiguousarray(angles, dtype=np.float64)

    P = np.zeros((levels, levels, len(distances), len(angles)),
                 dtype=np.uint32, order='C')

    # count co-occurences
    _glcm_loop(image, distances, angles, levels, P)

    # make each GLMC symmetric
    if symmetric:
        Pt = np.transpose(P, (1, 0, 2, 3))
        P = P + Pt

    # normalize each GLMC
    if normed:
        P = P.astype(np.float64)
        glcm_sums = np.apply_over_axes(np.sum, P, axes=(0, 1))
        glcm_sums[glcm_sums == 0] = 1
        P /= glcm_sums

    return P


def greycoprops(P, prop='contrast'):
    """Calculate texture properties of a GLCM.

    Compute a feature of a grey level co-occurrence matrix to serve as
    a compact summary of the matrix. The properties are computed as
    follows:

    - 'contrast': :math:`\\sum_{i,j=0}^{levels-1} P_{i,j}(i-j)^2`
    - 'dissimilarity': :math:`\\sum_{i,j=0}^{levels-1}P_{i,j}|i-j|`
    - 'homogeneity': :math:`\\sum_{i,j=0}^{levels-1}\\frac{P_{i,j}}{1+(i-j)^2}`
    - 'ASM': :math:`\\sum_{i,j=0}^{levels-1} P_{i,j}^2`
    - 'energy': :math:`\\sqrt{ASM}`
    - 'correlation':
        .. math:: \\sum_{i,j=0}^{levels-1} P_{i,j}\\left[\\frac{(i-\\mu_i) \\
                  (j-\\mu_j)}{\\sqrt{(\\sigma_i^2)(\\sigma_j^2)}}\\right]


    Parameters
    ----------
    P : ndarray
        Input array. `P` is the grey-level co-occurrence histogram
        for which to compute the specified property. The value
        `P[i,j,d,theta]` is the number of times that grey-level j
        occurs at a distance d and at an angle theta from
        grey-level i.
    prop : {'contrast', 'dissimilarity', 'homogeneity', 'energy', \
            'correlation', 'ASM'}, optional
        The property of the GLCM to compute. The default is 'contrast'.

    Returns
    -------
    results : 2-D ndarray
        2-dimensional array. `results[d, a]` is the property 'prop' for
        the d'th distance and the a'th angle.

    References
    ----------
    .. [1] The GLCM Tutorial Home Page,
           http://www.fp.ucalgary.ca/mhallbey/tutorial.htm

    Examples
    --------
    Compute the contrast for GLCMs with distances [1, 2] and angles
    [0 degrees, 90 degrees]

    >>> image = np.array([[0, 0, 1, 1],
    ...                   [0, 0, 1, 1],
    ...                   [0, 2, 2, 2],
    ...                   [2, 2, 3, 3]], dtype=np.uint8)
    >>> g = greycomatrix(image, [1, 2], [0, np.pi/2], levels=4,
    ...                  normed=True, symmetric=True)
    >>> contrast = greycoprops(g, 'contrast')
    >>> contrast
    array([[ 0.58333333,  1.        ],
           [ 1.25      ,  2.75      ]])

    """
    assert_nD(P, 4, 'P')

    (num_level, num_level2, num_dist, num_angle) = P.shape
    assert num_level == num_level2
    assert num_dist > 0
    assert num_angle > 0

    # create weights for specified property
    I, J = np.ogrid[0:num_level, 0:num_level]
    if prop == 'contrast':
        weights = (I - J) ** 2
    elif prop == 'dissimilarity':
        weights = np.abs(I - J)
    elif prop == 'homogeneity':
        weights = 1. / (1. + (I - J) ** 2)
    elif prop in ['ASM', 'energy', 'correlation']:
        pass
    else:
        raise ValueError('%s is an invalid property' % (prop))

    # compute property for each GLCM
    if prop == 'energy':
        asm = np.apply_over_axes(np.sum, (P ** 2), axes=(0, 1))[0, 0]
        results = np.sqrt(asm)
    elif prop == 'ASM':
        results = np.apply_over_axes(np.sum, (P ** 2), axes=(0, 1))[0, 0]
    elif prop == 'correlation':
        results = np.zeros((num_dist, num_angle), dtype=np.float64)
        I = np.array(range(num_level)).reshape((num_level, 1, 1, 1))
        J = np.array(range(num_level)).reshape((1, num_level, 1, 1))
        diff_i = I - np.apply_over_axes(np.sum, (I * P), axes=(0, 1))[0, 0]
        diff_j = J - np.apply_over_axes(np.sum, (J * P), axes=(0, 1))[0, 0]

        std_i = np.sqrt(np.apply_over_axes(np.sum, (P * (diff_i) ** 2),
                                           axes=(0, 1))[0, 0])
        std_j = np.sqrt(np.apply_over_axes(np.sum, (P * (diff_j) ** 2),
                                           axes=(0, 1))[0, 0])
        cov = np.apply_over_axes(np.sum, (P * (diff_i * diff_j)),
                                 axes=(0, 1))[0, 0]

        # handle the special case of standard deviations near zero
        mask_0 = std_i < 1e-15
        mask_0[std_j < 1e-15] = True
        results[mask_0] = 1

        # handle the standard case
        mask_1 = mask_0 == False
        results[mask_1] = cov[mask_1] / (std_i[mask_1] * std_j[mask_1])
    elif prop in ['contrast', 'dissimilarity', 'homogeneity']:
        weights = weights.reshape((num_level, num_level, 1, 1))
        results = np.apply_over_axes(np.sum, (P * weights), axes=(0, 1))[0, 0]

    return results


def local_binary_pattern(image, P, R, method='default'):
    """Gray scale and rotation invariant LBP (Local Binary Patterns).

    LBP is an invariant descriptor that can be used for texture classification.

    Parameters
    ----------
    image : (N, M) array
        Graylevel image.
    P : int
        Number of circularly symmetric neighbour set points (quantization of
        the angular space).
    R : float
        Radius of circle (spatial resolution of the operator).
    method : {'default', 'ror', 'uniform', 'var'}
        Method to determine the pattern.

        * 'default': original local binary pattern which is gray scale but not
            rotation invariant.
        * 'ror': extension of default implementation which is gray scale and
            rotation invariant.
        * 'uniform': improved rotation invariance with uniform patterns and
            finer quantization of the angular space which is gray scale and
            rotation invariant.
        * 'nri_uniform': non rotation-invariant uniform patterns variant
            which is only gray scale invariant [2]_.
        * 'var': rotation invariant variance measures of the contrast of local
            image texture which is rotation but not gray scale invariant.

    Returns
    -------
    output : (N, M) array
        LBP image.

    References
    ----------
    .. [1] Multiresolution Gray-Scale and Rotation Invariant Texture
           Classification with Local Binary Patterns.
           Timo Ojala, Matti Pietikainen, Topi Maenpaa.
           http://www.rafbis.it/biplab15/images/stories/docenti/Danielriccio/Articoliriferimento/LBP.pdf, 2002.
    .. [2] Face recognition with local binary patterns.
           Timo Ahonen, Abdenour Hadid, Matti Pietikainen,
           http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.214.6851,
           2004.
    """
    assert_nD(image, 2)

    methods = {
        'default': ord('D'),
        'ror': ord('R'),
        'uniform': ord('U'),
        'nri_uniform': ord('N'),
        'var': ord('V')
    }
    image = np.ascontiguousarray(image, dtype=np.double)
    output = _local_binary_pattern(image, P, R, methods[method.lower()])
    return output

def multiblock_local_binary_pattern(int_image, x, y, width, height):
    """Multi-block local binary pattern.

    MB-LBP is an extension of LBP that can be computed on many
    scales in a constant time using integral image. It consists of
    9 equal-sized rectangles. Sum of pixels' intensity values
    in each of them are compared to the central rectangle and
    depending on comparison result, the feature descriptor is
    computed.

    Parameters
    ----------
    int_image : (N, M) array
        Integral image.
    x : int
        X-coordinate of top left corner of a rectangle containing feature.
    y : int
        Y-coordinate of top left corner of a rectangle containing feature.
    width : int
        Width of one of 9 equal rectangles that will be used to compute
        a feature.
    height : int
        Height of one of 9 equal rectangles that will be used to compute
        a feature.

    Returns
    -------
    output : int
        8bit MB-LBP feature descriptor.

    References
    ----------
    .. [1] Face Detection Based on Multi-Block LBP
           Representation. Lun Zhang, Rufeng Chu, Shiming Xiang, Shengcai Liao,
           Stan Z. Li
           http://www.cbsr.ia.ac.cn/users/scliao/papers/Zhang-ICB07-MBLBP.pdf
    """

    # Top-left coordinates of central rectangle
    central_rect_x = x + width
    central_rect_y = y + height

    # Sum of intensity values of central rectangle
    central_rect_val = integrate(int_image,
                                 central_rect_y,
                                 central_rect_x,
                                 central_rect_y + height - 1,
                                 central_rect_x + width - 1)

    # Offsets of neighbour rectangles relative to central one.
    # It has order starting from top left and going clockwise
    neighbour_rect_offsets = ((-1, -1), (0, -1), (1, -1),
                              (1, 0), (1, 1), (0, 1),
                              (-1, 1), (-1, 0))

    lbp_code = 0

    for element_num, offset in enumerate(neighbour_rect_offsets):

        offset_x, offset_y = offset

        current_rect_x = central_rect_x + offset_x * width
        current_rect_y = central_rect_y + offset_y * height
        current_rect_val = integrate(int_image,
                                     current_rect_y,
                                     current_rect_x,
                                     current_rect_y + height - 1,
                                     current_rect_x + width - 1)

        has_greater_value = current_rect_val >= central_rect_val

        # If current rectangle's intensity value is bigger
        # make corresponding bit to 1.
        lbp_code |= has_greater_value << element_num

        print lbp_code

    return lbp_code

def visualize_multiblock_lbp(img, x, y, width, height, lbp_code=0):

    import matplotlib.patches as patches
    import matplotlib.pyplot as plt

    plt.imshow(img)
    img_desc = plt.gca()
    plt.set_cmap('gray')

    # Offsets of neighbour rectangles relative to central one.
    # It has order starting from top left and going clockwise
    neighbour_rect_offsets = ((-1, -1), (0, -1), (1, -1),
                              (1, 0), (1, 1), (0, 1),
                              (-1, 1), (-1, 0))

    # Top-left coordinates of central rectangle
    central_rect_x = x + width
    central_rect_y = y + height

    for element_num, offset in enumerate(neighbour_rect_offsets):

        offset_x, offset_y = offset

        current_rect_x = central_rect_x + offset_x * width
        current_rect_y = central_rect_y + offset_y * height

        has_greater_value = lbp_code & (1 << element_num)

        # Hatch the rectangles that has less
        # intensity than the central rectangle.
        hatch = '\\'

        if has_greater_value:
            hatch = ''

        img_desc.add_patch(
            patches.Rectangle(
                (current_rect_x, current_rect_y),
                width,
                height,
                fill=False,
                hatch=hatch,
                color='w'
            )
        )

    plt.show()
