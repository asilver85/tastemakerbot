from django.shortcuts import render
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from models import User, UserRecommendation, UserLikeDislike
import json
import random
import datetime

NUM_RECS_IN_PROFILE = 5
# Create your views here.

@csrf_exempt
def get_recommendation(request):
    
    result = {'status' : 'ok'}

    if request.method != 'POST':
        result = get_error_response(400, 'invalid request method')
        return JsonResponse(result)

    try:
        data = json.loads(request.body)

        if 'username' not in data:
            result = get_error_response(400, 'missing username')
            return JsonResponse(result)

        username = data['username']
        user = get_user(username)
        last_rec_ids = get_last_rec_ids(user)

        rec_user = None
        if 'recommendation_from' in data:
            rec_username = data['recommendation_from']
            rec_user = get_user_no_create(rec_username)
            if rec_user is None:
                result = get_error_response(400, 'could not find user')
                return JsonResponse(result)

        rec = get_rand_rec(user.id, last_rec_ids, rec_user)
        
        if rec is None:
            ### try to get rec without specifying last ones
            rec = get_rand_rec(user.id, [], rec_user)

            if rec is None:
                result = get_error_response(500, 'no valid recommendations')
                return JsonResponse(result)

        update_user_profile(user, rec.id, last_rec_ids)

        result['recommendation_id'] = rec.id
        result['recommendation_link'] = rec.link
        result['recommendation_desc'] = rec.description
        result['recommendation_from'] = rec.user.slack_username
        result['likes'] = rec.likes
        result['dislikes'] = rec.dislikes

    except Exception as e:
        print str(e)
        result = get_error_response(500, 'unknown error')

    return JsonResponse(result)

@csrf_exempt
def add_recommendation(request):

    result = {'status' : 'ok'}

    if request.method != 'POST':
        result = get_error_response(400, 'invalid request method')
        return JsonResponse(result)

    data = json.loads(request.body)

    if (
        'username' not in data or
        'link' not in data or
        'desc' not in data
        ):
        result = get_error_response(400, 'missing data')
        return JsonResponse(result)

    try:

        ### check if recommendation already exists ###
        if UserRecommendation.objects.filter(link=data['link']).exists():
            result = get_error_response(409, 'recommendation already exists')
            return JsonResponse(result)

        user = get_user(data['username'])
        new_rec = UserRecommendation(
                            user=user,
                            link=data['link'],
                            description=data['desc'],
                            gracenote_id=None,
                            likes=0,
                            dislikes=0,
                            timestamp=timezone.now())

        new_rec.save()

        result['recommendation_id'] = new_rec.id

    except:
        result = get_error_response(500, 'unknown error')

    return JsonResponse(result)

@csrf_exempt
def like_dislike(request):
    result = {'status' : 'ok'}

    if request.method != 'POST':
        result = get_error_response(400, 'invalid request method')
        return JsonResponse(result)

    data = json.loads(request.body)

    if (
        'username' not in data or
        'recommendation_id' not in data or
        'like' not in data
        ):
        result = get_error_response(400, 'missing data')
        return JsonResponse(result)

    try:

        rec = UserRecommendation.objects.get(id=data['recommendation_id'])
        
        ### you cannot like your own!!! ###
        if username == rec.user.slack_username:
            result = get_error_response(409, 'cannot like own recommendation')
            return JsonResponse(result)

        if result['like']:
            rec.likes += 1

        else:
            rec.dislikes += 1

        rec.save()
        user = get_user(data['username'])
        update_user_like_dislike(user, rec, data['like'])

    except:
        result = get_error_response(500, 'unkown error')

    return JsonResponse(result)

def add_gracenoteid(request):
    result = {'status' : 'ok'}

    if request.method != 'POST':
        result = get_error_response(400, 'invalid request method')
        return JsonResponse(result)

    data = json.loads(request.body)

    if (
        'recommendation_id' not in data or
        'gracenote_id' not in data
        ):
        result = get_error_response(400, 'missing data')
        return JsonResponse(result)

    try:
        user_rec = UserRecommendation.objects.get(id=data['recommendation_id'])
        user_rec.gracenote_id = str(data['gracenote_id'])
        user_rec.save()
        
    except:
        result = get_error_response(500, 'unknown error')

    return JsonResponse(result)

def get_user_no_create(username):
    if User.objects.filter(slack_username=username).exists():
        return User.objects.get(slack_username=username)

    return None

def get_user(username):
    if not User.objects.filter(slack_username=username).exists():
        new_user = User(slack_username=username, profile='')
        new_user.save()
        return new_user

    return User.objects.get(slack_username=username)

def get_error_response(error_id, error_message):
    result = {
            'status' : 'error',
            'error_id' : error_id,
            'error_message' : error_message
        }

    return result

def get_last_rec_ids(user):
    last_rec_ids = []
    if len(user.profile) > 0:
        last_rec_ids = [int(rec_id) for rec_id in user.profile.split(',')]

    return last_rec_ids

def get_rand_rec(userid, last_rec_ids, rec_user):

    print 'HERE %d %d' % (userid, len(last_rec_ids))
    print rec_user is None

    if rec_user is not None:
        candidates = UserRecommendation.objects.filter(user__id=rec_user.id).exclude(id__in=last_rec_ids)
    else:
        candidates = UserRecommendation.objects.exclude(user__id=userid).exclude(id__in=last_rec_ids)
    
    if len(candidates) == 0:
        return None

    rand_index = random.randint(1, len(candidates)) - 1

    return candidates[rand_index]

def update_user_profile(user, new_rec_id, last_rec_ids):
    
    last_rec_ids = [new_rec_id] + last_rec_ids
    if len(last_rec_ids) > NUM_RECS_IN_PROFILE:
        del last_rec_ids[-1]

    user.profile = ','.join(map(str, last_rec_ids)) 

    user.save()

def update_user_like_dislike(user, rec, like):

    if not UserLikeDislike.filter(user__id=user.id, rec__id=rec.id).exists():
        user_like_dislike = UserLikeDislike(user=user, rec=rec, like=like, timestamp=timezone.now())
        user_like_dislike.save()
    else:
        user_like_dislike = UserLikeDislike.objects.get(user__id=user.id, rec__id=rec.id)
        
        user_like_dislike.like = like
        user_like_dislike.timestamp = timezone.now()
        user_like_dislike.save()
