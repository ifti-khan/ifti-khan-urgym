from django.shortcuts import (
    render, redirect, reverse, get_object_or_404, HttpResponse)
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.conf import settings

from .forms import OrderForm
from .models import Order, OrderLineItem

from products.models import Product
from profiles.models import UserProfile
from profiles.forms import UserProfileForm
from trolley.contexts import trolley_contents

import stripe
import json


@require_POST
def cache_checkout_data(request):
    """
    This block of code is making a post request with the client secrect key
    from the payment intent and then splitting secret and storing it pid.
    Then modifying the payment intent with the metadata which contains the
    shopping trolley data, if they want to save there delivery info and
    and the user.
    """
    try:
        pid = request.POST.get('client_secret').split('_secret')[0]
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.PaymentIntent.modify(pid, metadata={
            'trolley': json.dumps(request.session.get('trolley', {})),
            'save_del_info': request.POST.get('save_del_info'),
            'username': request.user,
        })
        # Setting up error handling with toast messages
        return HttpResponse(status=200)
    except Exception as e:
        messages.error(request, 'Sorry, your payment cannot be \
            processed right now. Please try again later.')
        return HttpResponse(content=e, status=400)


def checkout(request):
    """
    Creating the checkout view which uses the shopping trolley session
    and if a session has not yet been created then a message will infrom
    the user that there shopping trolley is empty and redirect them back
    to the products page. Also creating an empty instance of the order form,
    creating the checkout template, adding the order form to the context
    processor and lastly rendering it all out.
    """
    # Setting the public and secret key vars for stripe from main settings
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    stripe_secret_key = settings.STRIPE_SECRET_KEY

    # Checking to see if the method is post and get the
    # shopping trolley session. Also putting the order form data
    # into a dictionary.
    if request.method == 'POST':
        trolley = request.session.get('trolley', {})

        form_data = {
            'full_name': request.POST['full_name'],
            'email_address': request.POST['email_address'],
            'phone_number': request.POST['phone_number'],
            'address_line1': request.POST['address_line1'],
            'address_line2': request.POST['address_line2'],
            'town_or_city': request.POST['town_or_city'],
            'county': request.POST['county'],
            'postcode': request.POST['postcode'],
            'country': request.POST['country'],
        }
        order_form = OrderForm(form_data)
        # If the order form is valid then it will be saved
        if order_form.is_valid():
            # This stops multiple save event to the db
            order = order_form.save(commit=False)

            # Getting the payment intent id, adding the shopping
            # trolley to the model by getting and dumping the
            # shopping trolley to json and then saving the order
            pid = request.POST.get('client_secret').split('_secret')[0]
            order.stripe_pid = pid
            order.original_trolley = json.dumps(trolley)
            order.save()

            # This code was taken from my trolley context.py and modified
            for item_id, item_data in trolley.items():
                try:
                    # Getting product id out of the trolley, if value is an
                    # integer, then product has no sizes and save the
                    # order line item.
                    product = Product.objects.get(id=item_id)
                    if isinstance(item_data, int):
                        order_line_item = OrderLineItem(
                            order=order,
                            product=product,
                            quantity=item_data,
                        )
                        order_line_item.save()
                    else:
                        # Code taken from my trolley context.py and modified
                        # This is for orders which have sizes and iterates
                        # through each line item and saves them.
                        for size, quantity in item_data['item_size'].items():
                            order_line_item = OrderLineItem(
                                order=order,
                                product=product,
                                quantity=quantity,
                                product_size=size,
                            )
                            order_line_item.save()
                # Error message for product if not found in database, the order
                # is deleted and user is taken back to the view trolley page
                except Product.DoesNotExist:
                    messages.error(request, (
                        "One of the products in your shopping trolley, \
                            could not be found in the database, \
                                Please call us for assistance!")
                    )
                    order.delete()
                    return redirect(reverse('view_trolley'))
            # This session is for users who want to save there delivery
            # info to there personal profile and if all is successful then
            # the user will be taken to the checkout success page.
            request.session['save_del_info'] = 'save-del-info' in request.POST
            return redirect(
                reverse('checkout_complete', args=[order.order_number]))
        else:
            messages.error(request, 'There was an error with your order form. \
                Please check the information you have entered.')
    else:
        trolley = request.session.get('trolley', {})
        if not trolley:
            messages.error(request, "Your shopping trolley is empty,\
            please add a product to your shopping trolley")
            return redirect(reverse('products'))

        # Storing current shopping trolley in var called current_trolley
        # Also getting the final total key from the current trolley and
        # setting the stripe total as integer
        current_trolley = trolley_contents(request)
        total = current_trolley['final_total']
        stripe_total = round(total * 100)

        # Setting the secrect key on stripe, creating the payment
        # intent and setting the stripe currency from main setting file
        stripe.api_key = stripe_secret_key
        intent = stripe.PaymentIntent.create(
            amount=stripe_total,
            currency=settings.STRIPE_CURRENCY,
        )

        # This block of code  will prefill the order form with
        # any info the user maintains in there profile page
        if request.user.is_authenticated:
            try:
                profile = UserProfile.objects.get(user=request.user)
                order_form = OrderForm(initial={
                    # This info is coming from the user profile model
                    'full_name': profile.default_full_name,
                    'email_address': profile.default_email_address,
                    'phone_number': profile.default_phone_number,
                    'address_line1': profile.default_address_line1,
                    'address_line2': profile.default_address_line2,
                    'town_or_city': profile.default_town_or_city,
                    'county': profile.default_county,
                    'postcode': profile.default_postcode,
                    'country': profile.default_country,

                })
            except UserProfile.DoesNotExist:
                order_form = OrderForm()
        else:
            order_form = OrderForm()

    # Stripe message if dev forgets to add stripe public key to env
    if not stripe_public_key:
        messages.warning(request, 'Stripe public key is missing. \
            Please set in your environment')

    template = 'checkout/checkout.html'
    context = {
        'order_form': order_form,
        # Stripe public key
        'stripe_public_key': stripe_public_key,
        # Client secret key with intent
        'client_secret': intent.client_secret,
    }

    return render(request, template, context)


def checkout_complete(request, order_number):
    """
    This view is for the checkout success letting the user know
    that the payment was successful and order has been completed
    """

    # Getting the delivery info session for the profile page,
    # also getting the previous orders order number to include
    # in the toast message to the user along with additional info
    save_del_info = request.session.get('save_del_info')
    order = get_object_or_404(Order, order_number=order_number)

    # Checking the the user is logged in
    if request.user.is_authenticated:
        profile = UserProfile.objects.get(user=request.user)
        # Attach the user's profile to the order
        order.user_profile = profile
        order.save()

        # Save the users order info
        if save_del_info:
            # Profile data dictionary
            profile_data = {
                'default_full_name': order.full_name,
                'default_email_address': order.email_address,
                'default_phone_number': order.phone_number,
                'default_address_line1': order.address_line1,
                'default_address_line2': order.address_line2,
                'default_town_or_city': order.town_or_city,
                'default_county': order.county,
                'default_postcode': order.postcode,
                'default_country': order.country,
            }
            user_profile_form = UserProfileForm(profile_data, instance=profile)
            if user_profile_form.is_valid():
                user_profile_form.save()

            messages.success(request, f'Order successfully completed! \
                Your order number is {order_number}. A confirmation \
                email will be sent to {order.email_address}.')
        else:
            if not save_del_info:
                messages.success(request, f'Order successfully completed! \
                Your order number is {order_number}. A confirmation \
                email will be sent to {order.email_address}.')

    # Deleting users shopping trolley session
    if 'trolley' in request.session:
        del request.session['trolley']

    # Setting the template and context to be rendered
    template = 'checkout/checkout_complete.html'
    context = {
        'order': order,
    }

    return render(request, template, context)
