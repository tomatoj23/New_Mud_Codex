from django.urls import path

from .views import character_creation_profile_list_view, character_list_view

urlpatterns = [
    path(
        "character-creation-profiles",
        character_creation_profile_list_view,
        name="character-creation-profile-list",
    ),
    path("characters", character_list_view, name="character-list"),
]
