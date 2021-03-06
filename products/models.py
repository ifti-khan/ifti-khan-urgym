from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):

    # Adding a meta class specifying a verbose name of categories
    # instead of Django default category name on the admin page
    class Meta:
        verbose_name_plural = 'Categories'

    # Setting the programmatic name
    category_name = models.CharField(max_length=254)
    # Setting the friendly name
    category_friendly_name = models.CharField(
        max_length=254, null=True, blank=True)

    # Creating a string method for
    # the category name
    def __str__(self):
        return self.category_name

    # Creating a model method to
    # to return the friendly name
    def get_friendly_name(self):
        return self.category_friendly_name


class Product(models.Model):
    """
    Below you will find the product model which contains
    the key fields to store product information.
    Null and Blank true have been used throughout the model
    fields to make them optional.
    """
    category = models.ForeignKey(
        'Category', null=True, blank=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=254)
    product_description = models.TextField()
    product_price = models.DecimalField(max_digits=6, decimal_places=2)
    product_rating = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    sku = models.CharField(
        max_length=254, null=True, blank=True)
    product_sizes = models.BooleanField(null=True, blank=True)
    product_image = models.ImageField(null=True, blank=True)
    product_image_url = models.URLField(
        max_length=1024, null=True, blank=True)

    def __str__(self):
        return self.product_name


class Review(models.Model):
    """
    Below you will see the review model for all products.
    The only fields that will show in the form itself will be
    the review title, review rating and the review message
    """
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    review_title = models.CharField(max_length=250)
    review_rating = models.DecimalField(
        max_digits=2, decimal_places=1)
    review_message = models.TextField(max_length=1000)
    date_created = models.DateField(auto_now_add=True)
    time_created = models.TimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username
