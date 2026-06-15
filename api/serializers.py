"""Shared serializer helpers for REST API v1."""

from rest_framework import serializers


class PublicUsernameMixin:
    """Hide username when the account uses anonymous identity mode."""

    def get_public_username(self, user):
        if user is None:
            return None
        return user.username if user.show_username_publicly else None


class PublicUsernameField(serializers.SerializerMethodField):
    def to_representation(self, value):
        user = value
        if user is None:
            return None
        return user.username if user.show_username_publicly else None
