from django.http import HttpResponseForbidden
from requests import request
from inventory.models import Moderator
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class UserIsModerator(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return len(Moderator.objects.filter(user=self.request.user)) != 0

    def handle_no_permission(self):
        return HttpResponseForbidden("<h1>Only moderators can access this page!</h1>")
