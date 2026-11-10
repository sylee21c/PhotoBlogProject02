from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from blog import views

router = DefaultRouter()
router.register('Post', views.PostViewSet, basename='post-api')
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api-auth/', include('rest_framework.urls')),
    path('api/token/', views.LoginTokenView.as_view(), name='api-token'),
    path('api/me/', views.account_profile, name='account-profile'),
    path('api/health/', views.health, name='health'),
    path('api_root/', include(router.urls)),
    path('', include('blog.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
