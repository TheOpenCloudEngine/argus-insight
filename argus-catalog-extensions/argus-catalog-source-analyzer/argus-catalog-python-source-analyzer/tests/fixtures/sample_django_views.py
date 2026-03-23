from django.db import connection
from django.http import JsonResponse


def dashboard_stats(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM authors")
        author_count = cursor.fetchone()[0]

        cursor.execute("SELECT b.title, a.name FROM books b JOIN authors a ON b.author_id = a.id ORDER BY b.published_date DESC LIMIT 10")
        recent_books = cursor.fetchall()

    return JsonResponse({"author_count": author_count, "recent_books": recent_books})


def bulk_update_ratings(request):
    with connection.cursor() as cursor:
        cursor.execute("UPDATE reviews SET rating = rating + 1 WHERE rating < 5")
