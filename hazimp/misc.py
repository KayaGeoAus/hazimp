# -*- coding: utf-8 -*-

# Copyright (C) 2012-2013  Geoscience Australia

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=W1202,W0612
"""
Functions that haven't found a proper module.
"""
import os
import sys
import inspect
from datetime import datetime

import logging
import tempfile
import errno
import boto3
from botocore.exceptions import ClientError
from zipfile import ZipFile

LOGGER = logging.getLogger(__name__)
import numpy
from numpy.random import random_sample, permutation

import pandas as pd
import geopandas as gpd

from git import Repo, InvalidGitRepositoryError

LOGGER = logging.getLogger(__name__)


_temporary_directory = None
_s3_client = None
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RESOURCE_DIR = os.path.join(ROOT_DIR, 'resources')
EXAMPLE_DIR = os.path.join(ROOT_DIR, 'examples')
INTID = 'internal_id'

DRIVERS = {'shp': 'ESRI Shapefile',
           'json': 'GeoJSON',
           'gpkg': 'GPKG'}

DATEFMT = '%Y-%m-%d %H:%M:%S %Z'


def csv2dict(filename, add_ids=False):
    """
    Read a csv file in and return the information as a dictionary
    where the key is the column names and the values are column arrays.

    :param add_ids: If True add a key, value of ids, from 0 to n
    :param filename: The csv file path string.
    """
    plain_dic = pd.read_csv(filename, skipinitialspace=True, index_col=False)

    if add_ids:
        # Add internal id info
        array_len = len(plain_dic[list(plain_dic.keys())[0]])
        plain_dic[INTID] = numpy.arange(array_len)
    return plain_dic


def instanciate_classes(module):
    """
    Create a dictionary of calc names (key) and the calc instance (value).

    :param module: ??
    """
    callable_instances = {}
    for _, obj in inspect.getmembers(module):
        if inspect.isclass(obj):
            instance = obj()
            if callable(instance):
                callable_instances[instance.call_funct] = instance
    return callable_instances

def mod_file_list(file_list, variable):
    """
    Modify the filename list for working with netcdf format files.

    For netcdf files, GDAL expects the filename to be of the form
    'NETCDF:"<filename>":<variable>', where variable is a valid
    variable in the netcdf file.

    :param file_list: List of files or a single file to be processed
    :param str variable: Variable name

    :returns: list of filenames, modified to the above format

    """

    if isinstance(file_list, str):
        file_list = [file_list]
    flist = []
    for f in file_list:
        flist.append(f'NETCDF:"{f}":{variable}')
    return flist

def mod_file_list(file_list, variable):
    """
    Modify the filename list for working with netcdf format files.

    For netcdf files, GDAL expects the filename to be of the form
    'NETCDF:"<filename>":<variable>', where variable is a valid
    variable in the netcdf file.

    :param file_list: List of files or a single file to be processed
    :param str variable: Variable name

    :returns: list of filenames, modified to the above format

    """

    if isinstance(file_list, str):
        file_list = [file_list]
    flist = []
    for f in file_list:
        flist.append(f'NETCDF:"{f}":{variable}')
    return flist


def mod_file_list(file_list, variable):
    """
    Modify the filename list for working with netcdf format files.

    For netcdf files, GDAL expects the filename to be of the form
    'NETCDF:"<filename>":<variable>', where variable is a valid
    variable in the netcdf file.

    :param file_list: List of files or a single file to be processed
    :param str variable: Variable name

    :returns: list of filenames, modified to the above format

    """

    if isinstance(file_list, str):
        file_list = [file_list]
    flist = []
    for f in file_list:
        flist.append(f'NETCDF:"{f}":{variable}')
    return flist


def get_required_args(func):
    """
    Get the arguments required in a function, from the function.

    :param func: The function that you need to know about.
    """

    # http://stackoverflow.com/questions/196960/
    # can-you-list-the-keyword-arguments-a-python-function-receives

    # *args and **kwargs are not required, so ignore them.
    args_and_defaults, _, _, default_vaules, _, _, _ = inspect.getfullargspec(func)
    defaults = []
    if default_vaules is None:
        args = args_and_defaults
    else:
        args = args_and_defaults[:-len(default_vaules)]
        defaults = args_and_defaults[-len(default_vaules):]
    return args, defaults


def squash_narray(ary):
    """
    Reduce an array to 1 dimension. Firstly try to average the values.
    If that doesn't work only take the first dimension.

    :param ary: the numpy array to be squashed.
    :returns: The ary array, averaged to 1d.
    """
    if ary.ndim > 1:
        try:
            d1_ary = ary.reshape((ary.shape[0], -1)).mean(axis=1)
        except TypeError:
            # Can't average, just take the first axis
            d1_ary = ary.reshape((ary.shape[0], -1))[:, 0]
    else:
        d1_ary = ary
    return d1_ary


def add(var, var2):
    """
    Add the values of two numpy arrays together.
    If the values are strings concatenate them.

    :param var: The values in this array are added.
    :param var2: The values in this array are added.
    :returns: The new column name, with the values of Var1 + var2.
    """
    try:
        result = numpy.asarray(var + var2)
    except TypeError:
        # Assume numpy array with strings
        result = numpy.asarray(numpy.core.defchararray.add(var, var2))
    return result


def weighted_values(values, probabilities, size, forced_random=None):
    """
    Return values weighted by the probabilities.

    precondition: The sum of probabilities should sum to 1
    Code from: goo.gl/oBo2zz

    :param values:  The values to go into the final array
    :param probabilities:  The probabilities of the values
    :param size: The array size/shape. Must be 1D.
    :return: The array of values, made using the probabilities
    """

    msg = "Due to numpy.digitize the array must be 1D. "
    assert len(size) == 1, msg

    assert isinstance(probabilities, numpy.ndarray)
    assert isinstance(values, numpy.ndarray)

    assert values.shape == probabilities.shape

    if not numpy.allclose(probabilities.sum(), 1.0, atol=0.01):
        msg = 'Weights should sum to 1.0, got ', probabilities
        raise RuntimeError(msg)

    # Re-normalise weights so they sum to 1 exactly
    probabilities = probabilities / abs(probabilities.sum())

    if forced_random is None:
        rand_array = random_sample(size)
    else:
        assert forced_random.shape == size
        rand_array = forced_random
    bins = numpy.add.accumulate(probabilities)
    return values[numpy.digitize(rand_array, bins)]


def sorted_dict_values(adict):
    """
    Given a dictionary return the sorted keys and values,
    sorting with respect to the keys.

    code from: goo.gl/Sb7Czw
    :param adict: A dictionary.
    :return: The sorted keys and the corresponding values
        as two lists.
    """
    keys = sorted(sorted(adict.keys()))
    return keys, [adict[key] for key in keys]


def permutate_att_values(dframe, fields, groupby=None):
    """
    Given a dataframe, return the dataframe with the values in
    ``fields`` permutated. If the ``groupby`` arg is given,
    then permutate the values of ``fields`` within each grouping of
    ``groupby``.

    :param dframe: A dataframe.
    :type dframe: ``pandas.DataFrame``
    :param fields: Name of a field to permutate, or a list of fields.
    :type fields: str or list.
    :param str groupby: Name of the field to group values by.

    :return: The same ``pandas.DataFrame``, with the values of ``fields``
             permutated.

    """
    newdf = dframe.copy()
    if isinstance(fields, str):
        fields = [fields]

    if groupby and groupby in dframe.columns:
        for field in fields:
            newdf[field] = \
                newdf.groupby(groupby)[field].transform(permutation)
    elif groupby and groupby not in dframe.columns:
        LOGGER.error(f"Cannot use {groupby} for permuting exposure attributes")
        LOGGER.error("The input expsoure data does not include that field")
        sys.exit()
    else:
        for field in fields:
            newdf[field] = newdf[field].transform(permutation)

    return newdf


def aggregate_loss_atts(dframe, groupby=None, kwargs=None):
    """
    Aggregate the impact data contained in a `pandas.DataFrame`

    :param dframe: `pandas.DataFrame` that contains impact data
    :param str groupby: A column in the `DataFrame` that corresponds to
    regions by which to aggregate data
    :param dict kwargs: A `dict` with keys of valid column names (from the
    `DataFrame`) and values being lists of aggregation functions to apply
    to the columns.

    For example::

    kwargs = {'REPLACEMENT_VALUE': ['mean', 'sum'],
              'structural_loss_ratio': ['mean', 'std']}

    See
    https://pandas.pydata.org/pandas-docs/stable/user_guide/groupby.html#aggregation
    for more guidance on using aggregation with `DataFrames`

    :returns: A `pandas.GroupBy` object.

    """
    grouped = dframe.groupby(groupby, as_index=False)

    outdf = grouped.agg(kwargs)
    outdf.columns = ['_'.join(col).strip() for col in outdf.columns.values]
    outdf.reset_index(col_level=1)
    outdf.columns = outdf.columns.get_level_values(0)
    return outdf


def get_file_mtime(file):
    """
    Retrieve the modified time of a file

    :param str file: Full path to a valid file

    :returns: ISO-format of the modification time of the file
    """
    dt = datetime.fromtimestamp(os.path.getmtime(file))
    return dt.strftime(DATEFMT)


def choropleth(dframe, boundaries, impactcode, bcode, filename):
    """
    Aggregate to geospatial boundaries and save to file

    :param dframe: `pandas.DataFrame` containing point data to be aggregated
    :param str boundaries: File name of a geospatial dataset that contains
                  geographical boundaries to serve as aggregation boundaries
    :param str impactcode: Field name in the `dframe` to aggregate by
    :param str bcode: Corresponding field name in the geospatial dataset.
    :param str filename: Destination filename. Must have a valid extension from
                   `shp`, `json` or `gpkg`.
    """
    # List of possible drivers for output:
    # See `import fiona; fiona.supported_drivers` for a complete list of
    # options, but we've only implemented a few to start with.

    left, right = mergefield = impactcode, bcode

    # TODO: Change to a function argument and configuration option
    report = {'REPLACEMENT_VALUE': 'sum',
              'structural_loss_ratio': 'mean',
              '0.2s gust at 10m height m/s': 'max'}

    aggregate = dframe.groupby(left).agg(report)
    shapes = gpd.read_file(boundaries)

    try:
        shapes['key'] = shapes[right].astype(int)
    except KeyError:
        LOGGER.error(f"{boundaries} does not contain an attribute {right}")
        sys.exit(1)

    result = shapes.merge(aggregate, left_on='key', right_index=True)
    driver = DRIVERS[os.path.splitext(filename)[1].replace('.', '')]
    if driver == 'ESRI Shapefile':
        LOGGER.debug("Changing field names for ESRI Shapefile")
        # Need to modify the field names, as ESRI truncates them
        colnames = {'REPLACEMENT_VALUE': 'REPVAL',
                    'structural_loss_ratio': 'slr_mean',
                    '0.2s gust at 10m height m/s': 'maxwind'}
        result = result.rename(columns=colnames)
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
        LOGGER.warning(f"{dirname} does not exist - trying to create it")
        os.makedirs(dirname)
    result.to_file(filename, driver=driver)


def get_git_commit():
    """
    Return the git commit hash, branch and datetime of the commit

    :returns: the commit hash and current branch if the code is maintained in a
    git repo. If not, the commit is "unknown", branch is empty and the datetime
    is set to be the modified time of the called python script
    (usually hazimp/main.py)

    """
    try:
        r = Repo(ROOT_DIR)
        commit = str(r.commit('HEAD'))
        branch = str(r.active_branch)
        dt = r.commit('HEAD').committed_datetime.strftime(DATEFMT)
    except InvalidGitRepositoryError:
        # We're not using a git repo
        commit = 'unknown'
        branch = ''
        f = os.path.realpath(__file__)
        mtime = os.path.getmtime(f)
        dt = datetime.fromtimestamp(mtime).strftime(DATEFMT)

    return commit, branch, dt

def get_s3_client():
    """
    Returns service client for S3. It eliminates initialising service client if AWS
    path is not used.
    """
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client

def get_temporary_directory():
    """
    Returns temporary directory to store file from and to S3 for local processing.
    """
    global _temporary_directory
    if _temporary_directory is None:
        _temporary_directory = tempfile.TemporaryDirectory(prefix='HazImp-')
    return _temporary_directory.name


def s3_path_segments_from_vsis3(s3_path):
    """
    Function to extract bucket name, key and filename from path specified using
    GDAL Virtual File Systems conventions
    :param str s3_path: Path to S3 location in /vsis3/bucket/key format.
    :returns  bucket name, bucket key and file name
    """
    s3_path_segments = s3_path.split('/')
    if s3_path_segments[0] != '' or s3_path_segments[1] != 'vsis3':
        raise ValueError('Invalid path: ', [s3_path, s3_path_segments])
    file_name = s3_path_segments[-1]
    bucket_name = s3_path_segments[2]
    bucket_key = '/'.join(s3_path_segments[3:])
    return bucket_name, bucket_key, file_name

def download_from_s3(s3_source_path, destination_directory, ignore_exception=False):
    """
    Function to download a S3 file into local directory.
    :param str s3_source_path: S3 path of the file.
    :param str destination_directory: Local directory location to
    """
    [bucket_name, bucket_key, file_name] = s3_path_segments_from_vsis3(s3_source_path)
    file_path = os.path.join(destination_directory, file_name)
    LOGGER.info("Downloading from S3 bucket: {0}, key: {1}, file: {2}"
                .format(bucket_name, bucket_key, file_path))
    try:
        get_s3_client().download_file(bucket_name, bucket_key, file_path)
    except ClientError as e:
        if not ignore_exception:
            LOGGER.exception("S3 read error: {0}".format(file_name))
            raise e
    return file_path


def download_file_from_s3_if_needed(s3_source_path, default_file_extension_inside_zip='.shp',
                                    destination_directory=None):
    """
    This function checks if the path is pointing to S3. If S3 path is specified, this function
    downloads the file to a temporary directory and return local file path. In case of shapefile,
    4 other files (with extensions .shx, .dbf, .prj and .shp.xml) are downloaded from S3. If zip
    file path is provided, the zip file is extracted and .shp file path is returned.
    :param str s3_source_path: S3 path of the file.
    :param str default_file_extension_inside_zip: If a zipped file is provided, this
                extension shill be used to find the the target file
    :param str destination_directory: Local directory location to
    :returns: downloaded file path in local file system.
    """
    if not s3_source_path.startswith('/vsis3/'):
        return s3_source_path
    if destination_directory is None:
        destination_directory = get_temporary_directory()
    if s3_source_path.endswith('.shp'):
        file_name_base = s3_source_path[0:-4]
        download_from_s3(file_name_base + '.shx', destination_directory)
        download_from_s3(file_name_base + '.dbf', destination_directory)
        download_from_s3(file_name_base + '.prj', destination_directory)
        download_from_s3(file_name_base + '.shp.xml', destination_directory, True)
        return download_from_s3(s3_source_path, destination_directory)
    elif s3_source_path.endswith('.zip'):
        zip_file_path = download_from_s3(s3_source_path, destination_directory)
        [_, _, zip_file_name] = s3_path_segments_from_vsis3(s3_source_path)
        [extracted_directory, _] = os.path.splitext(os.path.join(destination_directory, zip_file_name))
        LOGGER.debug('Extracting: ' + zip_file_path)
        with ZipFile(zip_file_path, 'r') as zipObj:
            zipObj.extractall(extracted_directory)
        for root, dirs, files in os.walk(extracted_directory):
            target_files = list(filter(lambda file: file.endswith(default_file_extension_inside_zip), files))
            if len(target_files) > 0:
                LOGGER.debug("Target file inside zip found: " + target_files[0])
                return os.path.join(extracted_directory, target_files[0])
        LOGGER.error("Target file inside zip not found!")
    else:
        return download_from_s3(s3_source_path, destination_directory)


def create_temporary_file_path_for_s3_if_applicable(destination_path):
    """
    This function checks if the path is pointing to S3. If yes, it changes file
    path to a file in temporary directory which will be uploaded after later.
    :param str destination_path: S3 path of the file.
    :returns: local file path, bucket name and bucket key.
    """
    if not destination_path.startswith('/vsis3/'):
        return destination_path, None, None
    [bucket_name, bucket_key, file_name] = s3_path_segments_from_vsis3(destination_path)
    return os.path.join(get_temporary_directory(), file_name), bucket_name, bucket_key


def upload_to_s3_if_applicable(local_path, bucket_name, bucket_key, ignore_exception=False):
    """
    Function to upload files from local directory to s3.
    :param str local_path: Local directory path containing files to upload.
    :param str bucket_name: Destination S3 bucket name
    :param str bucket_key: Destination S3 bucket key for the file
    :param bool ignore_exception: ignore any exception related to file upload.
                            Set true for optional files.
    """
    if bucket_name is None or bucket_key is None:
        return
    if not os.path.isfile(local_path):
        if not ignore_exception:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), local_path)
        return
    LOGGER.info("Uploading to S3 bucket: {0}, key: {1}, file: {2}"
                .format(bucket_name, bucket_key, local_path))
    try:
        get_s3_client().upload_file(local_path, bucket_name, bucket_key)
    except ClientError as e:
        if not ignore_exception:
            LOGGER.exception("S3 write error: {0}".format(local_path))
            raise e
