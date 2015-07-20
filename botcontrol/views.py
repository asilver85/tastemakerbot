from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.template import RequestContext, loader
from django.conf import settings

import os
import subprocess
# Create your views here.

scriptfile = 'tastemakerbot.py'

@login_required
def index(request):

    template = loader.get_template('botcontrol.html')
    context = RequestContext(request)
    
    return HttpResponse(template.render(context))    

@login_required
def signon(request):

    startBot()
    
    response = {
        'error' : 0,
    }
    
    return JsonResponse(response);

def startBot():

    pathScript = os.path.join(settings.BASE_DIR, 'libs', scriptfile)

    args = ['python', pathScript]
    subprocess.Popen(args)




