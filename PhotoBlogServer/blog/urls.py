from django.urls import path
from . import views
urlpatterns = [path('', views.post_list, name='post-list'),
               path('post/new/', views.post_new, name='post-new'),
               path('post/<int:pk>/edit/', views.post_edit, name='post-edit'),
               path('post/<int:pk>/delete/', views.post_delete, name='post-delete'),
               path('post/<int:pk>/', views.post_detail, name='post-detail')]
