from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.urls import reverse

from .models import HelpCategory, HelpArticle, ArticleVote


@login_required
def help_overview(request):
    query = request.GET.get('q', '').strip()
    if query:
        return redirect(f"{reverse('help_center:search')}?q={query}")

    categories = HelpCategory.objects.annotate(
        article_count=Count('articles', filter=Q(articles__is_published=True))
    )

    context = {
        'categories': categories,
    }
    return render(request, 'help_center/overview.html', context)


@login_required
def help_category(request, slug):
    category = get_object_or_404(HelpCategory, slug=slug)
    query    = request.GET.get('q', '').strip()

    articles = category.articles.filter(is_published=True)

    if query:
        articles = articles.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    context = {
        'category': category,
        'articles': articles,
        'query':    query,
    }
    return render(request, 'help_center/category.html', context)


from itertools import groupby   # add this import at the top

@login_required
def help_search(request):
    query   = request.GET.get('q', '').strip()
    results = HelpArticle.objects.none()
    grouped_results = []

    if query:
        results = (
            HelpArticle.objects
            .filter(is_published=True)
            .filter(Q(title__icontains=query) | Q(content__icontains=query))
            .select_related('category')
            .order_by('category__title', 'order', 'title')
        )

        # Group by category in Python — avoids Django 6.0 {% regroup %} breakage
        for category, articles in groupby(results, key=lambda a: a.category):
            article_list = list(articles)
            grouped_results.append({
                'category': category,
                'articles': article_list,
                'count':    len(article_list),
            })

    context = {
        'query':           query,
        'grouped_results': grouped_results,
        'result_count':    sum(g['count'] for g in grouped_results),
    }
    return render(request, 'help_center/search_results.html', context)

@login_required
def help_article_detail(request, slug):
    article   = get_object_or_404(HelpArticle, slug=slug, is_published=True)
    user_vote = ArticleVote.objects.filter(article=article, user=request.user).first()

    if request.method == 'POST':
        vote_value = request.POST.get('vote', '').strip()

        if vote_value not in ('helpful', 'not_helpful'):
            messages.error(request, 'Invalid feedback option.')
            return redirect(reverse('help_center:article_detail', kwargs={'slug': slug}))

        is_helpful = vote_value == 'helpful'

        with transaction.atomic():
            if user_vote:
                if user_vote.is_helpful == is_helpful:
                    messages.info(request, 'You have already submitted that feedback.')
                else:
                    user_vote.is_helpful = is_helpful
                    user_vote.save()
                    messages.success(request, 'Your feedback has been updated.')
            else:
                ArticleVote.objects.create(
                    article    = article,
                    user       = request.user,
                    is_helpful = is_helpful,
                )
                messages.success(request, 'Thank you for your feedback!')

        return redirect(reverse('help_center:article_detail', kwargs={'slug': slug}))

    related_articles = (
        HelpArticle.objects
        .filter(category=article.category, is_published=True)
        .exclude(pk=article.pk)
        .order_by('order', 'title')[:4]
    )

    context = {
        'article':          article,
        'user_vote':        user_vote,
        'related_articles': related_articles,
    }
    return render(request, 'help_center/article_detail.html', context)