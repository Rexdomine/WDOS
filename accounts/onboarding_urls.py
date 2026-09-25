from django.urls import path
from . import onboarding, onboarding_review
app_name = 'onboarding'
urlpatterns = [path('onboarding/photo/', onboarding.photo, name='photo'), path('onboarding/privacy/', onboarding.privacy, name='privacy'), path('onboarding/review/<int:account_id>/', onboarding_review.review, name='review'), path('onboarding/', onboarding.start, name='start'), path('onboarding/<int:step>/', onboarding.step, name='step')]
