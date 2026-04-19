from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime
import os

from .models import SchoolAnnouncement
from academics.models import SchoolSupportedClasses

# Remainder of file (if any) or just leave it clean if empty.
# In this case, there was only announcement_add which is now moved to announcement_views.py
