from django.shortcuts import render


# ═══════════════════════════════════════════════════════════════════════════════
#  COVER / LANDING
# ═══════════════════════════════════════════════════════════════════════════════

def cover_page(request):
    return render(request, 'dashboard/cover.html')