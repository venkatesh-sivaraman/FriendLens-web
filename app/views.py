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

### MARK: CF Code

try:
    import cognitive_face as CF
except:
    import pip

    def install(package):
        pip.main(['install', package, '--user'])

    install('cognitive-face')

    import cognitive_face as CF


name_of_group = "kavya_friends_1"

fb_ids = [("100008532641869","Venkatesh Sivaraman"),("100006541209232","Karunya Sethuraman"),
          ("100001019659920","Rene Garcia"),("100002495596576","Mira Partha"),("100003239273542","Samyu Yagati"),
          ("100003046714844","Noah Moroze"),("100002460778633","Michael Zhang"),("100007818076486","Kavya Ravi")]

# In[2]:

def detect_face(img_url):
    '''returns the id,location of the face within the image'''
    return CF.face.detect(img_url)


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
        output_suggestions.append(CF.face.identify([j['faceId'] for j in i],name_of_group))
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
                outputs.append((CF.person.get(name_of_group,p_id)['name'],f_id,rect))
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
    CF.Key.set(KEY)

    BASE_URL = 'https://eastus.api.cognitive.microsoft.com/face/v1.0/' # Replace with your regional Base URL
    CF.BaseUrl.set(BASE_URL)

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
