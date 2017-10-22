"""
Definition of views.
"""

import os
from django.conf import settings
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.template import RequestContext
from datetime import datetime
from django import forms
from django.views.decorators.csrf import csrf_exempt
import json

import os.path
import time

import requests

DEFAULT_BASE_URL = 'https://westus.api.cognitive.microsoft.com/face/v1.0/'

TIME_SLEEP = 1


class CognitiveFaceException(Exception):
    """Custom Exception for the python SDK of the Cognitive Face API.

    Attributes:
        status_code: HTTP response status code.
        code: error code.
        msg: error message.
    """

    def __init__(self, status_code, code, msg):
        super(CognitiveFaceException, self).__init__()
        self.status_code = status_code
        self.code = code
        self.msg = msg

    def __str__(self):
        return ('Error when calling Cognitive Face API:\n'
                '\tstatus_code: {}\n'
                '\tcode: {}\n'
                '\tmessage: {}\n').format(self.status_code, self.code,
                                          self.msg)


class Key(object):
    """Manage Subscription Key."""

    @classmethod
    def set(cls, key):
        """Set the Subscription Key."""
        cls.key = key

    @classmethod
    def get(cls):
        """Get the Subscription Key."""
        if not hasattr(cls, 'key'):
            cls.key = None
        return cls.key


class BaseUrl(object):
    @classmethod
    def set(cls, base_url):
        cls.base_url = base_url

    @classmethod
    def get(cls):
        if not hasattr(cls, 'base_url') or not cls.base_url:
            cls.base_url = DEFAULT_BASE_URL
        return cls.base_url


def request(method, url, data=None, json=None, headers=None, params=None):
    # pylint: disable=too-many-arguments
    """Universal interface for request."""

    # Make it possible to call only with short name (without BaseUrl).
    if not url.startswith('https://'):
        url = BaseUrl.get() + url

    # Setup the headers with default Content-Type and Subscription Key.
    headers = headers or {}
    if 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/json'
    headers['Ocp-Apim-Subscription-Key'] = Key.get()

    response = requests.request(
        method, url, params=params, data=data, json=json, headers=headers)

    # Handle result and raise custom exception when something wrong.
    result = None
    # `person_group.train` return 202 status code for success.
    if response.status_code not in (200, 202):
        try:
            error_msg = response.json()['error']
        except:
            raise CognitiveFaceException(response.status_code,
                                         response.status_code, response.text)
        raise CognitiveFaceException(response.status_code,
                                     error_msg.get('code'),
                                     error_msg.get('message'))

    # Prevent `response.json()` complains about empty response.
    if response.text:
        result = response.json()
    else:
        result = {}

    return result


def parse_image(image):
    """Parse the image smartly and return metadata for request.

    First check whether the image is a URL or a file path or a file-like object
    and return corresponding metadata.

    Args:
        image: A URL or a file path or a file-like object represents an image.

    Returns:
        a three-item tuple consist of HTTP headers, binary data and json data
        for POST.
    """
    if hasattr(image, 'read'):  # When image is a file-like object.
        headers = {'Content-Type': 'application/octet-stream'}
        data = image.read()
        return headers, data, None
    elif os.path.isfile(image):  # When image is a file path.
        headers = {'Content-Type': 'application/octet-stream'}
        data = open(image, 'rb').read()
        return headers, data, None
    else:  # Default treat it as a URL (string).
        headers = {'Content-Type': 'application/json'}
        json = {'url': image}
        return headers, None, json


def wait_for_training(person_group_id):
    """Wait for the finish of person_group training."""
    idx = 1
    while True:
        res = CF.person_group.get_status(person_group_id)
        if res['status'] in ('succeeded', 'failed'):
            break
        print('The training of Person Group {} is onging: #{}'.format(
            person_group_id, idx))
        time.sleep(2**idx)
        idx += 1


def clear_face_lists():
    """[Dangerous] Clear all the face lists and all related persisted data."""
    face_lists = CF.face_list.lists()
    time.sleep(TIME_SLEEP)
    for face_list in face_lists:
        face_list_id = face_list['faceListId']
        CF.face_list.delete(face_list_id)
        print('Deleting Face List {}'.format(face_list_id))
        time.sleep(TIME_SLEEP)


def clear_person_groups():
    """[Dangerous] Clear all the person gourps and all related persisted data.
    """
    person_groups = CF.person_group.lists()
    time.sleep(TIME_SLEEP)
    for person_group in person_groups:
        person_group_id = person_group['personGroupId']
        CF.person_group.delete(person_group_id)
        print('Deleting Person Group {}'.format(person_group_id))
        time.sleep(TIME_SLEEP)


def add_face(image, face_list_id, user_data=None, target_face=None):
    """Add a face to a face list.

    The input face is specified as an image with a `target_face` rectangle. It
    returns a `persisted_face_id` representing the added face, and
    `persisted_face_id` will not expire. Note `persisted_face_id` is different
    from `face_id` which represents the detected face by `face.detect`.

    Args:
        image: A URL or a file path or a file-like object represents an image.
        face_list_id: Valid character is letter in lower case or digit or '-'
            or '_', maximum length is 64.
        user_data: Optional parameter. User-specified data about the face list
            for any purpose. The maximum length is 1KB.
        target_face: Optional parameter. A face rectangle to specify the target
            face to be added into the face list, in the format of
            "left,top,width,height". E.g. "10,10,100,100". If there are more
            than one faces in the image, `target_face` is required to specify
            which face to add. No `target_face` means there is only one face
            detected in the entire image.

    Returns:
        A new `persisted_face_id`.
    """
    url = 'facelists/{}/persistedFaces'.format(face_list_id)
    headers, data, json = util.parse_image(image)
    params = {
        'userData': user_data,
        'targetFace': target_face,
    }

    return util.request(
        'POST', url, headers=headers, params=params, json=json, data=data)


def create(face_list_id, name=None, user_data=None):
    """Create an empty face list with user-specified `face_list_id`, `name` and
    an optional `user_data`. Up to 64 face lists are allowed to exist in one
    subscription.

    Args:
        face_list_id: Valid character is letter in lower case or digit or '-'
            or '_', maximum length is 64.
        name: Name of the created face list, maximum length is 128.
        user_data: Optional parameter. User-defined data for the face list.
            Length should not exceed 16KB.

    Returns:
        An empty response body.
    """
    name = name or face_list_id
    url = 'facelists/{}'.format(face_list_id)
    json = {
        'name': name,
        'userData': user_data,
    }

    return util.request('PUT', url, json=json)


def delete_face(face_list_id, persisted_face_id):
    """Delete an existing face from a face list (given by a `persisted_face_id`
    and a `face_list_id`). Persisted image related to the face will also be
    deleted.

    Args:
        face_list_id: Valid character is letter in lower case or digit or '-'
            or '_', maximum length is 64.
        persisted_face_id: `persisted_face_id` of an existing face. Valid
            character is letter in lower case or digit or '-' or '_', maximum
            length is 64.

    Returns:
        An empty response body.
    """
    url = 'facelists/{}/persistedFaces/{}'.format(face_list_id,
                                                  persisted_face_id)

    return util.request('DELETE', url)


def delete(face_list_id):
    """Delete an existing face list according to `face_list_id`. Persisted face
    images in the face list will also be deleted.

    Args:
        face_list_id: Valid character is letter in lower case or digit or '-'
            or '_', maximum length is 64.

    Returns:
        An empty response body.
    """
    url = 'facelists/{}'.format(face_list_id)

    return util.request('DELETE', url)


def get(face_list_id):
    """Retrieve a face list's information, including `face_list_id`, `name`,
    `user_data` and faces in the face list. Face list simply represents a list
    of faces, and could be treated as a searchable data source in
    `face.find_similars`.

    Args:
        face_list_id: Valid character is letter in lower case or digit or '-'
            or '_', maximum length is 64.

    Returns:
        The face list's information.
    """
    url = 'facelists/{}'.format(face_list_id)

    return util.request('GET', url)


def lists():
    """Retrieve information about all existing face lists. Only `face_list_id`,
    `name` and `user_data` will be returned. Try `face_list.get` to retrieve
    face information inside face list.

    Returns:
        An array of face list.
    """
    url = 'facelists'

    return util.request('GET', url)


def update(face_list_id, name=None, user_data=None):
    """Update information of a face list, including `name` and `user_data`.
    Face List simply represents a list of persisted faces, and could be treated
    as a searchable data source in `face.find_similars`.

    Args:
        face_list_id: Valid character is letter in lower case or digit or '-'
            or '_', maximum length is 64.
        name: Name of the created face list, maximum length is 128.
        user_data: Optional parameter. User-defined data for the face list.
            Length should not exceed 16KB.

    Returns:
        An empty response body.
    """
    url = 'facelists/{}'.format(face_list_id)
    json = {
        'name': name,
        'userData': user_data,
    }

    return util.request('PATCH', url, json=json)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: face.py
Description: Face section of the Cognitive Face API.
"""



def detect(image, face_id=True, landmarks=False, attributes=''):
    """Detect human faces in an image and returns face locations, and
    optionally with `face_id`s, landmarks, and attributes.

    Args:
        image: A URL or a file path or a file-like object represents an image.
        face_id: [Optional] Return faceIds of the detected faces or not. The
            default value is true.
        landmarks: [Optional] Return face landmarks of the detected faces or
            not. The default value is false.
        attributes: [Optional] Analyze and return the one or more specified
            face attributes in the comma-separated string like
            "age,gender". Supported face attributes include age, gender,
            headPose, smile, facialHair, glasses and emotion.
            Note that each face attribute analysis has additional
            computational and time cost.

    Returns:
        An array of face entries ranked by face rectangle size in descending
        order. An empty response indicates no faces detected. A face entry may
        contain the corresponding values depending on input parameters.
    """
    url = 'detect'
    headers, data, json = util.parse_image(image)
    params = {
        'returnFaceId': face_id and 'true' or 'false',
        'returnFaceLandmarks': landmarks and 'true' or 'false',
        'returnFaceAttributes': attributes,
    }

    return util.request(
        'POST', url, headers=headers, params=params, json=json, data=data)


def find_similars(face_id,
                  face_list_id=None,
                  face_ids=None,
                  max_candidates_return=20,
                  mode='matchPerson'):
    """Given query face's `face_id`, to search the similar-looking faces from a
    `face_id` array or a `face_list_id`.

    Parameter `face_list_id` and `face_ids` should not be provided at the same
    time.

    Args:
        face_id: `face_id` of the query face. User needs to call `face.detect`
            first to get a valid `face_id`. Note that this `face_id` is not
            persisted and will expire in 24 hours after the detection call.
        face_list_id: An existing user-specified unique candidate face list,
            created in `face_list.create`. Face list contains a set of
            `persisted_face_ids` which are persisted and will never expire.
        face_ids: An array of candidate `face_id`s. All of them are created by
            `face.detect` and the `face_id`s will expire in 24 hours after the
            detection call. The number of `face_id`s is limited to 1000.
        max_candidates_return: Optional parameter. The number of top similar
            faces returned. The valid range is [1, 1000]. It defaults to 20.
        mode: Optional parameter. Similar face searching mode. It can be
            "matchPerson" or "matchFace". It defaults to "matchPerson".

    Returns:
        An array of the most similar faces represented in `face_id` if the
        input parameter is `face_ids` or `persisted_face_id` if the input
        parameter is `face_list_id`.
    """
    url = 'findsimilars'
    json = {
        'faceId': face_id,
        'faceListId': face_list_id,
        'faceIds': face_ids,
        'maxNumOfCandidatesReturned': max_candidates_return,
        'mode': mode,
    }

    return util.request('POST', url, json=json)


def group(face_ids):
    """Divide candidate faces into groups based on face similarity.

    Args:
        face_ids: An array of candidate `face_id`s created by `face.detect`.
            The maximum is 1000 faces.

    Returns:
        one or more groups of similar faces (ranked by group size) and a
        messyGroup.
    """
    url = 'group'
    json = {
        'faceIds': face_ids,
    }

    return util.request('POST', url, json=json)


def identify(face_ids,
             person_group_id,
             max_candidates_return=1,
             threshold=None):
    """Identify unknown faces from a person group.

    Args:
        face_ids: An array of query `face_id`s, created by the `face.detect`.
            Each of the faces are identified independently. The valid number of
            `face_ids` is between [1, 10].
        person_group_id: `person_group_id` of the target person group, created
            by `person_group.create`.
        max_candidates_return: Optional parameter. The range of
            `max_candidates_return` is between 1 and 5 (default is 1).
        threshold: Optional parameter. Confidence threshold of identification,
            used to judge whether one face belongs to one person. The range of
            confidence threshold is [0, 1] (default specified by algorithm).

    Returns:
        The identified candidate person(s) for each query face(s).
    """
    url = 'identify'
    json = {
        'personGroupId': person_group_id,
        'faceIds': face_ids,
        'maxNumOfCandidatesReturned': max_candidates_return,
        'confidenceThreshold': threshold,
    }

    return util.request('POST', url, json=json)


def verify(face_id, another_face_id=None, person_group_id=None,
           person_id=None):
    """Verify whether two faces belong to a same person or whether one face
    belongs to a person.

    For face to face verification, only `face_id` and `another_face_id` is
    necessary. For face to person verification, only `face_id`,
    `person_group_id` and `person_id` is needed.

    Args:
        face_id: `face_id` of one face, comes from `face.detect`.
        another_face_id: `face_id` of another face, comes from `face.detect`.
        person_group_id: Using existing `person_group_id` and `person_id` for
            fast loading a specified person. `person_group_id` is created in
            `person_group.create`.
        person_id: Specify a certain person in a person group. `person_id` is
            created in `person.create`.

    Returns:
        The verification result.
    """
    url = 'verify'
    json = {}
    if another_face_id:
        json.update({
            'faceId1': face_id,
            'faceId2': another_face_id,
        })
    else:
        json.update({
            'faceId': face_id,
            'personGroupId': person_group_id,
            'personId': person_id,
        })

    return util.request('POST', url, json=json)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: person_group.py
Description: Person Group section of the Cognitive Face API.
"""



def create(person_group_id, name=None, user_data=None):
    """Create a new person group with specified `person_group_id`, `name` and
    user-provided `user_data`.

    Args:
        person_group_id: User-provided `person_group_id` as a string. The valid
            characters include numbers, English letters in lower case, '-' and
            '_'.  The maximum length of the personGroupId is 64.i
        name: Person group display name. The maximum length is 128.
        user_data: User-provided data attached to the person group. The size
            limit is 16KB.

    Returns:
        An empty response body.
    """
    name = name or person_group_id
    url = 'persongroups/{}'.format(person_group_id)
    json = {
        'name': name,
        'userData': user_data,
    }

    return util.request('PUT', url, json=json)


def delete(person_group_id):
    """Delete an existing person group. Persisted face images of all people in
    the person group will also be deleted.

    Args:
        person_group_id: The `person_group_id` of the person group to be
            deleted.

    Returns:
        An empty response body.
    """
    url = 'persongroups/{}'.format(person_group_id)

    return util.request('DELETE', url)


def get(person_group_id):
    """Retrieve the information of a person group, including its `name` and
    `user_data`. This API returns person group information only, use
    `person.lists` instead to retrieve person information under the person
    group.

    Args:
        person_group_id: `person_group_id` of the target person group.

    Returns:
        The person group's information.
    """
    url = 'persongroups/{}'.format(person_group_id)

    return util.request('GET', url)


def get_status(person_group_id):
    """Retrieve the training status of a person group (completed or ongoing).
    Training can be triggered by `person_group.train`. The training will
    process for a while on the server side.

    Args:
        person_group_id: `person_group_id` of the target person group.

    Returns:
        The person group's training status.
    """
    url = 'persongroups/{}/training'.format(person_group_id)

    return util.request('GET', url)


def lists(start=None, top=None):
    """List person groups and their information.

    Args:
        start: Optional parameter. List person groups from the least
            `person_group_id` greater than the "start". It contains no more
            than 64 characters. Default is empty.
        top: The number of person groups to list, ranging in [1, 1000]. Default
            is 1000.

    Returns:
        An array of person groups and their information (`person_group_id`,
        `name` and `user_data`).
    """
    url = 'persongroups'
    params = {
        'start': start,
        'top': top,
    }

    return util.request('GET', url, params=params)


def train(person_group_id):
    """Queue a person group training task, the training task may not be started
    immediately.

    Args:
        person_group_id: Target person group to be trained.

    Returns:
        An empty JSON body.
    """
    url = 'persongroups/{}/train'.format(person_group_id)

    return util.request('POST', url)


def update(person_group_id, name=None, user_data=None):
    """Update an existing person group's display `name` and `user_data`. The
    properties which does not appear in request body will not be updated.

    Args:
        person_group_id: `person_group_id` of the person group to be updated.
        name: Optional parameter. Person group display name. The maximum length
            is 128.
        user_data: Optional parameter. User-provided data attached to the
            person group. The size limit is 16KB.

    Returns:
        An empty response body.
    """
    url = 'persongroups/{}'.format(person_group_id)
    json = {
        'name': name,
        'userData': user_data,
    }

    return util.request('PATCH', url, json=json)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: person.py
Description: Person section of the Cognitive Face API.
"""



def add_face(image,
             person_group_id,
             person_id,
             user_data=None,
             target_face=None):
    """Add a representative face to a person for identification. The input face
    is specified as an image with a `target_face` rectangle. It returns a
    `persisted_face_id` representing the added face and this
    `persisted_face_id` will not expire. Note `persisted_face_id` is different
    from `face_id` which represents the detected face by `face.detect`.

    Args:
        image: A URL or a file path or a file-like object represents an image.
        person_group_id: Specifying the person group containing the target
            person.
        person_id: Target person that the face is added to.
        user_data: Optional parameter. User-specified data about the face list
            for any purpose. The maximum length is 1KB.
        target_face: Optional parameter. A face rectangle to specify the target
            face to be added into the face list, in the format of
            "left,top,width,height". E.g. "10,10,100,100". If there are more
            than one faces in the image, `target_face` is required to specify
            which face to add. No `target_face` means there is only one face
            detected in the entire image.

    Returns:
        A new `persisted_face_id`.
    """
    url = 'persongroups/{}/persons/{}/persistedFaces'.format(
        person_group_id, person_id)
    headers, data, json = util.parse_image(image)
    params = {
        'userData': user_data,
        'targetFace': target_face,
    }

    return util.request(
        'POST', url, headers=headers, params=params, json=json, data=data)


def create(person_group_id, name, user_data=None):
    """Create a new person in a specified person group. A newly created person
    have no registered face, you can call `person.add` to add faces to the
    person.

    Args:
        person_group_id: Specifying the person group containing the target
            person.
        name: Display name of the target person. The maximum length is 128.
        user_data: Optional parameter. User-specified data about the face list
            for any purpose. The maximum length is 1KB.

    Returns:
        A new `person_id` created.
    """
    url = 'persongroups/{}/persons'.format(person_group_id)
    json = {
        'name': name,
        'userData': user_data,
    }

    return util.request('POST', url, json=json)


def delete(person_group_id, person_id):
    """Delete an existing person from a person group. Persisted face images of
    the person will also be deleted.

    Args:
        person_group_id: Specifying the person group containing the person.
        person_id: The target `person_id` to delete.

    Returns:
        An empty response body.
    """
    url = 'persongroups/{}/persons/{}'.format(person_group_id, person_id)

    return util.request('DELETE', url)


def delete_face(person_group_id, person_id, persisted_face_id):
    """Delete a face from a person. Relative image for the persisted face will
    also be deleted.

    Args:
        person_group_id: Specifying the person group containing the target
            person.
        person_id: Specifying the person that the target persisted face belongs
            to.
        persisted_face_id: The persisted face to remove. This
            `persisted_face_id` is returned from `person.add`.

    Returns:
        An empty response body.
    """
    url = 'persongroups/{}/persons/{}/persistedFaces/{}'.format(
        person_group_id, person_id, persisted_face_id)

    return util.request('DELETE', url)


def get(person_group_id, person_id):
    """Retrieve a person's information, including registered persisted faces,
    `name` and `user_data`.

    Args:
        person_group_id: Specifying the person group containing the target
            person.
        person_id: Specifying the target person.

    Returns:
        The person's information.
    """
    url = 'persongroups/{}/persons/{}'.format(person_group_id, person_id)

    return util.request('GET', url)


def get_face(person_group_id, person_id, persisted_face_id):
    """Retrieve information about a persisted face (specified by
    `persisted_face_ids`, `person_id` and its belonging `person_group_id`).

    Args:
        person_group_id: Specifying the person group containing the target
            person.
        person_id: Specifying the target person that the face belongs to.
        persisted_face_id: The `persisted_face_id` of the target persisted face
            of the person.

    Returns:
        The target persisted face's information (`persisted_face_id` and
        `user_data`).
    """
    url = 'persongroups/{}/persons/{}/persistedFaces/{}'.format(
        person_group_id, person_id, persisted_face_id)

    return util.request('GET', url)


def lists(person_group_id, start=None, top=None):
    """List `top` persons in a person group with `person_id` greater than
    `start`, and retrieve person information (including `person_id`, `name`,
    `user_data` and `persisted_face_ids` of registered faces of the person).

    Args:
        person_group_id: `person_group_id` of the target person group.
        start: List persons from the least `person_id` greater than this.
        top: The number of persons to list, rangeing in [1, 1000]. Default is
            1000;

    Returns:
        An array of person information that belong to the person group.
    """
    url = 'persongroups/{}/persons'.format(person_group_id)
    params = {
        'start': start,
        'top': top,
    }

    return util.request('GET', url, params=params)


def update(person_group_id, person_id, name=None, user_data=None):
    """Update `name` or `user_data` of a person.

    Args:
        person_group_id: Specifying the person group containing the target
            person.
        person_id: `person_id` of the target person.
        name: Target person's display name. Maximum length is 128.
        user_data: User-provided data attached to the person. Maximum length is
            16KB.

    Returns:
        An empty response body.
    """
    url = 'persongroups/{}/persons/{}'.format(person_group_id, person_id)
    json = {
        'name': name,
        'userData': user_data,
    }

    return util.request('PATCH', url, json=json)


def update_face(person_group_id, person_id, persisted_face_id, user_data=None):
    """Update a person persisted face's `user_data` field.

    Args:
        person_group_id: Specifying the person group containing the target
            person.
        person_id: `person_id` of the target person.
        persisted_face_id: `persisted_face_id` of the target face, which is
            persisted and will not expire.
        user_data: Optional parameter. Attach `user_data` to person's
            persisted face. The size limit is 1KB.

    Returns:
        An empty response body.
    """
    url = 'persongroups/{}/persons/{}/persistedFaces/{}'.format(
        person_group_id, person_id, persisted_face_id)
    json = {
        'userData': user_data,
    }

    return util.request('PATCH', url, json=json)

### MARK: CF Code


name_of_group = "kavya_friends_1"

fb_ids = [("100008532641869","Venkatesh Sivaraman"),("100006541209232","Karunya Sethuraman"),
          ("100001019659920","Rene Garcia"),("100002495596576","Mira Partha"),("100003239273542","Samyu Yagati"),
          ("100003046714844","Noah Moroze"),("100002460778633","Michael Zhang"),("100007818076486","Kavya Ravi")]

# In[2]:

def detect_face(img_url):
    '''returns the id,location of the face within the image'''
    return face.detect(img_url)


# In[3]:

def break_into_10s(list_of_faces):
    out = []
    a = len(list_of_faces)//10
    if len(list_of_faces)/10 != a:
        a+=1
    for i in range(a):
        out.append(list_of_faces[10*i:10*i+10])
    return out


# In[4]:

def imgurl_to_output_suggestions(img, name_of_group):
    faces = detect_face(img)
    tens_of_faces = break_into_10s(faces)
    output_suggestions = []
    for i in tens_of_faces:
        output_suggestions.append(face.identify([j['faceId'] for j in i],name_of_group))
    for i in range(len(output_suggestions)):
        for o in output_suggestions[i]:
            for j in faces:
                if o['faceId'] == j['faceId']:
                    o['faceRectangle'] = j['faceRectangle']
    return output_suggestions


# In[5]:

def process_output_suggestions(output_suggestions):
    outputs = []
    for x in range(len(output_suggestions)):
        for i in output_suggestions[x]:
            cand = i['candidates']
            f_id = i['faceId']
            rect = i['faceRectangle']
            conf_cand = []
            if cand!=[]:
                for j in cand:
                    conf_cand.append((j['confidence'],j['personId']))
            if conf_cand == []:
                outputs.append((None,f_id))
            else:
                m_conf = 0
                for c in conf_cand:
                    if m_conf<c[0]:
                        m_conf = c[0]
                for c in conf_cand:
                    if c[0] == m_conf:
                        p_id = c[1]
                outputs.append((person.get(name_of_group,p_id)['name'],f_id,rect))
    return outputs


# In[17]:

def clean_up(output):
    actual_output = []
    for i in output:
        if i[0]!=None:
            for x in fb_ids:
                if i[0] in x[1]:
                    fb_id = x[0]
            actual_output.append((i[0],i[2],fb_id))
    return actual_output


# In[18]:

def identify_friends(img_path):
    KEY = 'ce2b24ee78624530a94bb5fd79bec2eb' #primary
    Key.set(KEY)

    BASE_URL = 'https://eastus.api.cognitive.microsoft.com/face/v1.0/' # Replace with your regional Base URL
    BaseUrl.set(BASE_URL)

    #img_path = '' #path at which the image sent to server is hosted
    name_of_group = 'kavya_friends_1'
    o_s = imgurl_to_output_suggestions(img_path,name_of_group)
    out = process_output_suggestions(o_s)
    return clean_up(out)


class UploadFileForm(forms.Form):
    title = forms.CharField(max_length=50)
    file = forms.FileField()

def handle_uploaded_file(f):
    dest_path = os.path.join(settings.MEDIA_ROOT, 'img_1.jpg').replace('\\', '/')
    with open(dest_path, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
    return dest_path #os.path.join(settings.MEDIA_URL, 'img_1.jpg').replace('\\', '/')

@csrf_exempt
def getimg(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        dest_path = handle_uploaded_file(request.FILES['file'])
        results = identify_friends(dest_path)
        return HttpResponse(json.dumps(results))
    else:
        form = UploadFileForm()
    return HttpResponse("Don't know what to give you")

def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/index.html',
        context_instance = RequestContext(request,
        {
            'title':'Home Page',
            'year':datetime.now().year,
        })
    )

def contact(request):
    """Renders the contact page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/contact.html',
        context_instance = RequestContext(request,
        {
            'title':'Contact',
            'message':'Your contact page.',
            'year':datetime.now().year,
        })
    )

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/about.html',
        context_instance = RequestContext(request,
        {
            'title':'About',
            'message':'Your application description page.',
            'year':datetime.now().year,
        })
    )
