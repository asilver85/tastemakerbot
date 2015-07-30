from django.shortcuts import render
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.template import RequestContext, loader
from models import User, UserRecommendation, UserLikeDislike
from django.db.models import F
import json
import random
import datetime
import slg

NUM_RECS_IN_PROFILE = 10

COLLAB_FILTER_MAX_LIKES = 100
COLLAB_FILTER_MAX_SIMILAR_USERS = 3
COLLAB_FILTER_MIN_SCORE_SIMILAR_USERS = 3

MAX_CANDIDATES_RAND = 10
MAX_CANDIDATE_COLLAB_FILTER = 10

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
        user = get_user_or_create(username)
        last_rec_ids = get_last_rec_ids(user)

        rec_user = None
        if 'recommendation_from' in data:
            rec_username = data['recommendation_from']
            rec_user = get_user_no_create(rec_username)
            if rec_user is None:
                result = get_error_response(400, 'could not find user')
                return JsonResponse(result)

        rec = None
        ### if user specified, just get a random rec from user ###
        if rec_user is not None:
            rec = get_rand_rec(user.id, last_rec_ids, rec_user)
        else:
            rand_candidates = get_rand_recs_sample(user.id, last_rec_ids, rec_user, MAX_CANDIDATES_RAND)
            print 'HERE AFTER RAND'
            like_dislike_map, like_ids = get_user_like_info(user)
            print 'HERE likes: %d' % len(like_ids) 
            collab_filt_candidates = get_collab_filter_recs_sample(user, like_ids, like_dislike_map, last_rec_ids, MAX_CANDIDATE_COLLAB_FILTER)
            print 'AFTER COLLAB FILT'
            all_candidates = rand_candidates + collab_filt_candidates
            if len(all_candidates) > 0:
                rec = random.choice(all_candidates)

        ### if failed to get rec, get random rec with less history ###
        if rec is None:
            only_one_last_rec = last_rec_ids[0:1] if len(last_rec_ids) > 0 else []
            rec = get_rand_rec(user.id, only_one_last_rec, rec_user)

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

        user = get_user_or_create(data['username'])
        new_rec = UserRecommendation(
                            user=user,
                            link=data['link'],
                            description=data['desc'],
                            gracenote_id=None,
                            likes=0,
                            dislikes=0,
                            timestamp=timezone.now(),
                            is_youtube=is_youtube(data['link']))

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
        rec_user = UserRecommendation.objects.get(id=data['recommendation_id']).user.slack_username
        
        ### you cannot like your own!!! ###
        if data['username'] == rec_user:
            result = get_error_response(409, 'cannot like own recommendation')
            return JsonResponse(result)

        ### keep track of how many likes/dislikes to add to recommendation row ###
        ### i am doing it this way to prevent race condition ###
        likes_add = 0
        dislikes_add = 0

        if data['like']:
            likes_add += 1
        else:
            dislikes_add += 1

        ### check if user already liked/disliked this ###
        rec_id = data['recommendation_id']
        user = get_user_or_create(data['username'])
        user_like_dislike = get_user_like_dislike(user, rec_id)
        if user_like_dislike is not None:
            if user_like_dislike.like:
                likes_add -= 1
            else:
                dislikes_add -= 1

            user_like_dislike.like = data['like']
            user_like_dislike.timestamp = timezone.now()
            user_like_dislike.save()
        else:
            add_user_like_dislike(user, rec_id, data['like'])

        ### update likes/dislikes count for rec in one update ###
        UserRecommendation.objects.filter(id=data['recommendation_id']).update(likes=F('likes') + likes_add, dislikes=F('dislikes') + dislikes_add)

    except Exception as e:
        print str(e)
        result = get_error_response(500, 'unknown error')

    return JsonResponse(result)

def track_search(request, rec_id):
    rec = UserRecommendation.objects.get(id=rec_id)

    template = loader.get_template('tracksearch.html')
    context = RequestContext(request, {
        'rec_link': rec.link
    })

    return HttpResponse(template.render(context))

@csrf_exempt
def track_info(request):
    result = {'status' : 'ok'}

    if request.method != 'POST':
        result = get_error_response(400, 'invalid request method')
        return JsonResponse(result)

    data = json.loads(request.body)

    if 'track_id' not in data:
        result = get_error_response(400, 'missing data')
        return JsonResponse(result)

    track_data = {}
    try:
        track_profile = slg.getTrackProfile(data['track_id'])
        track_data['artist_name'] = track_profile.artistName
        track_data['artist_id'] = track_profile.artistId
        track_data['id'] = track_profile.id
        track_data['name'] = track_profile.name
        track_data['album'] = track_profile.albumName
        track_data['descriptors'] = []

        mood_cnt = 0
        for d in track_profile.descriptors:

            if d.descriptorCategory == slg.SlgDescriptorCategory.TEMPO:
                continue

            if d.descriptorCategory == slg.SlgDescriptorCategory.MOOD:
                if mood_cnt >= 10:
                    continue
                else:
                    mood_cnt += 1

            track_data['descriptors'].append({
                    'type' : slg.SlgDescriptorCategory.getString(d.descriptorCategory),
                    'id' : d.id,
                    'name' : d.name,
                    'weight' : d.weight
                })
    except Exception as e:
        print str(e)
        result = get_error_response(500, 'could not contact SLG')
        return JsonResponse(result)

    result['track_info'] = track_data
    
    return JsonResponse(result)

@csrf_exempt
def track_name_search(request):

    result = {'status' : 'ok'}

    if request.method != 'POST':
        result = get_error_response(400, 'invalid request method')
        return JsonResponse(result)

    data = json.loads(request.body)

    if 'artist_name' not in data or 'track_name' not in data:
        result = get_error_response(400, 'missing data')
        return JsonResponse(result)

    search_results = []

    try:
        server_data = slg.searchTrack(data['artist_name'], data['track_name'])
    except:
        result = get_error_response(500, 'could not contact SLG')
        return JsonResponse(result)

    for track in server_data:
        search_results.append({
                'artist_id' : str(track[0]),
                'artist_name' : track[1],
                'id' : str(track[2]),
                'name' : track[3]
            })

    result['search_results'] = search_results
    
    return JsonResponse(result)

@csrf_exempt
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

def is_youtube(link):
    return 'youtube.com' in link or 'youtu.be' in link

def get_user_no_create(username):
    if User.objects.filter(slack_username=username).exists():
        return User.objects.get(slack_username=username)

    return None

def get_user_or_create(username):
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
    candidates = get_rand_recs_sample(userid, last_rec_ids, rec_user, 1)
    if len(candidates) == 0:
        return None

    return candidates[0]

def get_rand_recs_sample(userid, last_rec_ids, rec_user, num_recs):
    if rec_user is not None:
        candidates = UserRecommendation.objects.filter(user__id=rec_user.id).exclude(id__in=last_rec_ids)
    else:
        candidates = UserRecommendation.objects.exclude(user__id=userid).exclude(id__in=last_rec_ids)

    if len(candidates) == 0:
        return []

    num_samples = num_recs if len(candidates) >= num_recs else len(candidates)
    return random.sample(candidates, num_samples)

def update_user_profile(user, new_rec_id, last_rec_ids):
    
    last_rec_ids = [new_rec_id] + last_rec_ids
    if len(last_rec_ids) > NUM_RECS_IN_PROFILE:
        del last_rec_ids[-1]

    user.profile = ','.join(map(str, last_rec_ids)) 

    user.save()

def get_user_like_dislike(user, rec_id):
    if UserLikeDislike.objects.filter(user__id=user.id, rec__id=rec_id).exists():
        return UserLikeDislike.objects.get(user__id=user.id, rec__id=rec_id)

    return None

def add_user_like_dislike(user, rec_id, like):
    if not UserLikeDislike.objects.filter(user__id=user.id, rec__id=rec_id).exists():
        user_like_dislike = UserLikeDislike(user=user, rec_id=rec_id, like=like, timestamp=timezone.now())
        user_like_dislike.save()

def get_user_like_info(user):
    like_dislike_map = {}
    like_list = []
    like_count = 0

    user_like_dislikes = UserLikeDislike.objects.filter(user__id=user.id)

    ### choose max COLLAB_FILTER_MAX_LIKES random likes ###
    
    ### shuffle list of user likes and dislikes ###
    list_indices = range(0, len(user_like_dislikes))
    random.shuffle(list_indices)

    for index in list_indices:
        user_like_dislike = user_like_dislikes[index]
        if user_like_dislike.like and like_count < COLLAB_FILTER_MAX_LIKES:
            like_dislike_map[user_like_dislike.rec.id] = True
            like_list.append(user_like_dislike.rec.id)
            like_count += 1 
        else:
            like_dislike_map[user_like_dislike.rec.id] = False

    return (like_dislike_map, like_list)

def get_collab_filter_recs_sample(user, like_ids, like_dislike_map, last_rec_ids, num_recs):

    if len(like_ids) == 0:
        return []

    last_rec_dict = {}

    for id in last_rec_ids:
        last_rec_dict[id] = True

    ### get all users with same likes ###
    shared_like_userids = UserLikeDislike.objects.exclude(user__id=user.id).filter(rec__id__in=like_ids, like=True).values_list('user_id', flat=True).distinct()

    if len(shared_like_userids) == 0:
        return []

    ## get likes dislikes of these users###
    other_like_dislikes = UserLikeDislike.objects.filter(user__id__in=shared_like_userids)

    similar_users = {}
    for userid in shared_like_userids:
        similar_users[userid] = {
            'score' : 0,
            'candidates' : []
        }
    
    for other_like_dislike in other_like_dislikes:
        recid = other_like_dislike.rec.id
        userid = other_like_dislike.user.id

        if recid in like_dislike_map:
            if other_like_dislike.like == like_dislike_map[recid]:
                similar_users[userid]['score'] += 1
            else:
                similar_users[userid]['score'] -= 1

        elif other_like_dislike.like and recid not in last_rec_dict:
            similar_users[userid]['candidates'].append(recid)

    ### sort by score ###
    simliar_users_list_sorted = sorted(similar_users.values(), key=lambda user: user['score'], reverse=True)
    count_sim_users = 0
    suggested_recids = []
    for user in simliar_users_list_sorted:
        if count_sim_users >= COLLAB_FILTER_MAX_SIMILAR_USERS:
            break

        if user['score'] < COLLAB_FILTER_MIN_SCORE_SIMILAR_USERS:
            break

        suggested_recids += user['candidates']

        count_sim_users += 1

    
    recs = UserRecommendation.objects.filter(id__in=suggested_recids)

    if len(recs) == 0:
        return []

    samples = num_recs if len(recs) >= num_recs else len(recs)
    return random.sample(recs, samples)






