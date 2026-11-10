from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db import transaction
import hashlib
import json
import uuid
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from .forms import PostForm
from .models import Post, EdgeUploadReceipt
from .permissions import IsOwnerOrReadOnly
from .serializers import PostSerializer
from .pagination import OptionalPostPagination

def visible_posts():
    return Post.objects.select_related('author').filter(published_date__lte=timezone.now())

def filter_posts(queryset, query, ordering):
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(text__icontains=query))
    choices = {'newest': ('-published_date', '-pk'), 'oldest': ('published_date', 'pk'), 'title': ('title', 'pk')}
    return queryset.order_by(*choices.get(ordering, choices['newest']))

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    pagination_class = OptionalPostPagination
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    def get_queryset(self):
        return filter_posts(visible_posts(), self.request.query_params.get('q', '').strip(),
                            self.request.query_params.get('ordering', 'newest'))
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def create(self, request, *args, **kwargs):
        event_id = request.headers.get('X-Event-ID')
        if not event_id:
            return super().create(request, *args, **kwargs)
        try:
            event_id = uuid.UUID(event_id)
        except ValueError:
            return Response({'detail': 'X-Event-ID must be a UUID.'}, status=400)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = serializer.validated_data['image']
        digest = hashlib.sha256()
        digest.update(json.dumps({k: serializer.validated_data[k] for k in ['title', 'text']},
                                 sort_keys=True, ensure_ascii=False).encode('utf-8'))
        for chunk in photo.chunks():
            digest.update(chunk)
        photo.seek(0)
        # Claim the event before writing its photo. The unique DB constraint
        # serializes repeated submissions without creating duplicate image files.
        with transaction.atomic():
            receipt, created = EdgeUploadReceipt.objects.get_or_create(
                author=request.user, event_id=event_id,
                defaults={'payload_sha256': digest.hexdigest()})
            if not created:
                if receipt.payload_sha256 != digest.hexdigest():
                    return Response({'detail': 'This event ID was already used for different content.'}, status=409)
                if receipt.post_id is None:
                    return Response({'detail': 'This event was already received and its post was deleted.'}, status=410)
                return Response(self.get_serializer(receipt.post).data, status=200,
                                headers={'X-Event-ID': str(event_id), 'X-Event-Replayed': 'true'})
            post = serializer.save(author=request.user)
            receipt.post = post
            receipt.save(update_fields=['post'])
        return Response(self.get_serializer(post).data, status=201,
                        headers={'X-Event-ID': str(event_id), 'X-Event-Replayed': 'false'})

class LoginThrottle(AnonRateThrottle):
    scope = 'login'

class LoginTokenView(ObtainAuthToken):
    throttle_classes = [LoginThrottle]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_profile(request):
    return Response({'id': request.user.pk, 'username': request.user.username})

def health(request):
    # A database query distinguishes an alive web process from a functioning service.
    return JsonResponse({'status': 'ok', 'service': 'PhotoBlog', 'posts': visible_posts().count()})

def post_list(request):
    query = request.GET.get('q', '').strip()
    ordering = request.GET.get('ordering', 'newest')
    return render(request, 'blog/list.html', {'posts': filter_posts(visible_posts(), query, ordering),
                                             'query': query, 'ordering': ordering})

def post_detail(request, pk):
    return render(request, 'blog/detail.html', {'post': get_object_or_404(visible_posts(), pk=pk)})

@login_required
def post_new(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('post-detail', pk=post.pk)
    return render(request, 'blog/edit.html', {'form': form, 'editing': False})

@login_required
@require_http_methods(['GET', 'POST'])
def post_edit(request, pk):
    post = get_object_or_404(visible_posts(), pk=pk)
    if post.author_id != request.user.pk:
        raise PermissionDenied
    form = PostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('post-detail', pk=post.pk)
    return render(request, 'blog/edit.html', {'form': form, 'post': post, 'editing': True})

@login_required
@require_http_methods(['GET', 'POST'])
def post_delete(request, pk):
    post = get_object_or_404(visible_posts(), pk=pk)
    if post.author_id != request.user.pk:
        raise PermissionDenied
    if request.method == 'POST':
        post.delete()
        return redirect('post-list')
    return render(request, 'blog/delete.html', {'post': post})
