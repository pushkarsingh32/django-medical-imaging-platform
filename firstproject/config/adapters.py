"""
Custom Headless Adapter for django-allauth.
Extends user serialization to include admin/staff status.
"""
from allauth.headless.adapter import DefaultHeadlessAdapter


class CustomHeadlessAdapter(DefaultHeadlessAdapter):
    """
    Custom adapter that includes is_staff and is_superuser in user data.

    This allows the frontend to know if the current user is an admin/staff member
    when calling the session endpoint: GET /_allauth/browser/v1/auth/session
    """

    def serialize_user(self, user):
        """
        Serialize user data including admin status.

        Args:
            user: Django User instance

        Returns:
            dict: User data with is_staff and is_superuser fields
        """
        # Get the default user data from parent class
        data = super().serialize_user(user)

        # Add admin/staff status fields
        # is_staff: Can access Django admin interface
        data['is_staff'] = user.is_staff

        # is_superuser: Has all permissions without explicitly assigning them
        data['is_superuser'] = user.is_superuser

        return data
