"""
Serializers for the notifications API.
"""
from django.core.exceptions import ValidationError
from rest_framework import serializers

from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.notifications.models import (
    CourseNotificationPreference,
    Notification,
    get_notification_channels
)
from .base_notification import COURSE_NOTIFICATION_APPS, COURSE_NOTIFICATION_TYPES
from .utils import filter_course_wide_preferences, remove_preferences_with_no_access


def add_info_to_notification_config(config_obj):
    """
    Add info of all notification types
    """

    config = config_obj['notification_preference_config']
    for notification_app, app_prefs in config.items():
        notification_types = app_prefs.get('notification_types', {})
        for notification_type, type_prefs in notification_types.items():
            if notification_type == "core":
                type_info = COURSE_NOTIFICATION_APPS.get(notification_app, {}).get('core_info', '')
            else:
                type_info = COURSE_NOTIFICATION_TYPES.get(notification_type, {}).get('info', '')
            type_prefs['info'] = type_info
    return config_obj


class CourseOverviewSerializer(serializers.ModelSerializer):
    """
    Serializer for CourseOverview model.
    """

    class Meta:
        model = CourseOverview
        fields = ('id', 'display_name')


class NotificationCourseEnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for CourseEnrollment model.
    """
    course = CourseOverviewSerializer()

    class Meta:
        model = CourseEnrollment
        fields = ('course',)


class UserCourseNotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer for user notification preferences.
    """
    course_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CourseNotificationPreference
        fields = ('id', 'course_name', 'course_id', 'notification_preference_config',)
        read_only_fields = ('id', 'course_name', 'course_id',)
        write_only_fields = ('notification_preference_config',)

    def to_representation(self, instance):
        """
        Override to_representation to add info of all notification types
        """
        preferences = super().to_representation(instance)
        course_id = self.context['course_id']
        user = self.context['user']
        preferences = add_info_to_notification_config(preferences)
        preferences = filter_course_wide_preferences(course_id, preferences)
        preferences = remove_preferences_with_no_access(preferences, user)
        return preferences

    def get_course_name(self, obj):
        """
        Returns course name from course id.
        """
        return CourseOverview.get_from_id(obj.course_id).display_name


class UserNotificationPreferenceUpdateSerializer(serializers.Serializer):
    """
    Serializer for user notification preferences update.
    """

    notification_app = serializers.CharField()
    value = serializers.BooleanField()
    notification_type = serializers.CharField(required=False)
    notification_channel = serializers.CharField(required=False)

    def validate(self, attrs):
        """
        Validation for notification preference update form
        """
        notification_app = attrs.get('notification_app')
        notification_type = attrs.get('notification_type')
        notification_channel = attrs.get('notification_channel')

        notification_app_config = self.instance.notification_preference_config

        if notification_type and not notification_channel:
            raise ValidationError(
                'notification_channel is required for notification_type.'
            )
        if notification_channel and not notification_type:
            raise ValidationError(
                'notification_type is required for notification_channel.'
            )

        if not notification_app_config.get(notification_app, None):
            raise ValidationError(
                f'{notification_app} is not a valid notification app.'
            )

        if notification_type:
            notification_types = notification_app_config.get(notification_app).get('notification_types')

            if not notification_types.get(notification_type, None):
                raise ValidationError(
                    f'{notification_type} is not a valid notification type.'
                )

        if notification_channel and notification_channel not in get_notification_channels():
            raise ValidationError(
                f'{notification_channel} is not a valid notification channel.'
            )

        return attrs

    def update(self, instance, validated_data):
        """
        Update notification preference config.
        """
        notification_app = validated_data.get('notification_app')
        notification_type = validated_data.get('notification_type')
        notification_channel = validated_data.get('notification_channel')
        value = validated_data.get('value')
        user_notification_preference_config = instance.notification_preference_config

        if notification_type and notification_channel:
            # Update the notification preference for specific notification type
            user_notification_preference_config[
                notification_app]['notification_types'][notification_type][notification_channel] = value

        else:
            # Update the notification preference for notification_app
            user_notification_preference_config[notification_app]['enabled'] = value

        instance.save()
        return instance


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for the Notification model.
    """
    class Meta:
        model = Notification
        fields = (
            'id',
            'app_name',
            'notification_type',
            'content_context',
            'content',
            'content_url',
            'last_read',
            'last_seen',
            'created',
        )
