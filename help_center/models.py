from django.db import models

# Create your models here.
from django.db import models
from django.utils.text import slugify
from django.conf import settings


class HelpCategory(models.Model):
    title       = models.CharField(max_length=100)
    slug        = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=60, default='bi-question-circle')  # Bootstrap Icons class
    order       = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering        = ['order', 'title']
        verbose_name    = 'Help Category'
        verbose_name_plural = 'Help Categories'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class HelpArticle(models.Model):
    category     = models.ForeignKey(HelpCategory, on_delete=models.CASCADE, related_name='articles')
    title        = models.CharField(max_length=200)
    slug         = models.SlugField(unique=True, blank=True)
    content      = models.TextField()           # stores HTML content
    roles        = models.JSONField(default=list, blank=True)  # e.g. ["admin", "bursar", "teacher", "parent"]
    order        = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering        = ['order', 'title']
        verbose_name    = 'Help Article'
        verbose_name_plural = 'Help Articles'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug      = base_slug
            counter   = 1
            while HelpArticle.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug    = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def helpful_count(self):
        return self.votes.filter(is_helpful=True).count()

    def not_helpful_count(self):
        return self.votes.filter(is_helpful=False).count()

    def total_votes(self):
        return self.votes.count()


class ArticleVote(models.Model):
    article    = models.ForeignKey(HelpArticle, on_delete=models.CASCADE, related_name='votes')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='help_votes')
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = ('article', 'user')
        verbose_name        = 'Article Vote'
        verbose_name_plural = 'Article Votes'

    def __str__(self):
        verdict = 'Helpful' if self.is_helpful else 'Not Helpful'
        return f'{self.user} → {self.article} ({verdict})'