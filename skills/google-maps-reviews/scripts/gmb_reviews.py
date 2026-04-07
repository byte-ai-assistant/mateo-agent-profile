#!/usr/bin/env python3
"""
Google My Business Reviews Manager
Fetches, analyzes, and manages reviews for CMR business locations.
"""

import os
import sys
import json
import argparse
import requests as _requests
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# API Scopes
SCOPES = ['https://www.googleapis.com/auth/business.manage']

# API base URLs (mybusiness v4 reviews endpoint still live; accounts moved to v1)
GMB_ACCOUNTS_BASE = 'https://mybusinessaccountmanagement.googleapis.com/v1'
GMB_REVIEWS_BASE  = 'https://mybusiness.googleapis.com/v4'
GMB_INFO_BASE     = 'https://mybusinessinformation.googleapis.com/v1'

def _get_token(creds):
    if not creds.valid:
        creds.refresh(Request())
    return creds.token

# Token storage path
TOKEN_PATH = os.path.expanduser('~/.openclaw/credentials/gmb_token.json')

# Credentials path
CREDENTIALS_PATH = os.path.expanduser(
    '~/Agent/mateo/credentials/client_secret_158668894120-i9ua7d8lo408q3sbrmvivv328aiaq2ei.apps.googleusercontent.com.json'
)

def get_credentials():
    """Get or refresh Google My Business API credentials."""
    creds = None
    
    # Load existing token
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                print(f"ERROR: Credentials file not found at {CREDENTIALS_PATH}", file=sys.stderr)
                print("Please download OAuth 2.0 credentials from Google Cloud Console", file=sys.stderr)
                sys.exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def list_accounts(creds):
    """List all Google My Business accounts."""
    headers = {'Authorization': f'Bearer {_get_token(creds)}'}
    r = _requests.get(f'{GMB_ACCOUNTS_BASE}/accounts', headers=headers)
    if not r.ok:
        print(f"Error listing accounts: {r.status_code} {r.text}", file=sys.stderr)
        return []
    return r.json().get('accounts', [])

def list_locations(creds, account_name):
    """List all locations for an account."""
    headers = {'Authorization': f'Bearer {_get_token(creds)}'}
    r = _requests.get(f'{GMB_ACCOUNTS_BASE}/{account_name}/locations', headers=headers, params={'readMask': 'name,title,storefrontAddress'})
    if not r.ok:
        print(f"Error listing locations: {r.status_code} {r.text}", file=sys.stderr)
        return []
    return r.json().get('locations', [])

def _full_location_path(location_name, account_name=None):
    """Ensure location_name includes the account prefix required by the v4 reviews API.
    list_locations() returns bare 'locations/ID' but the reviews endpoint needs
    'accounts/ACCOUNT_ID/locations/ID'."""
    if location_name.startswith('accounts/'):
        return location_name
    if account_name:
        return f'{account_name}/{location_name}'
    raise ValueError(f"Location '{location_name}' must be prefixed with account path. "
                     "Pass --account or use the full path: accounts/ID/locations/ID")

def get_location_rating(creds, location_name, account_name=None):
    """Fetch the aggregate averageRating for a location."""
    # mybusinessinformation API uses bare 'locations/{id}' — strip accounts prefix if present
    full_path = _full_location_path(location_name, account_name)
    if '/locations/' in full_path:
        location_id = full_path.split('/locations/')[-1]
        info_path = f'locations/{location_id}'
    else:
        info_path = full_path
    headers = {'Authorization': f'Bearer {_get_token(creds)}'}
    r = _requests.get(
        f'{GMB_INFO_BASE}/{info_path}',
        headers=headers,
        params={'readMask': 'averageRating,totalReviewCount'}
    )
    if not r.ok:
        print(f"Error fetching location rating: {r.status_code} {r.text}", file=sys.stderr)
        return None, None
    data = r.json()
    return data.get('averageRating'), data.get('totalReviewCount')


def list_reviews(creds, location_name, days_back=7, account_name=None):
    """List reviews for a location from the past N days."""
    headers = {'Authorization': f'Bearer {_get_token(creds)}'}
    full_path = _full_location_path(location_name, account_name)
    r = _requests.get(f'{GMB_REVIEWS_BASE}/{full_path}/reviews', headers=headers)
    if not r.ok:
        print(f"Error listing reviews: {r.status_code} {r.text}", file=sys.stderr)
        return []
    all_reviews = r.json().get('reviews', [])

    if days_back > 0:
        cutoff_date = datetime.now() - timedelta(days=days_back)
        filtered = []
        for review in all_reviews:
            review_date = datetime.fromisoformat(review['updateTime'].replace('Z', '+00:00'))
            if review_date.replace(tzinfo=None) >= cutoff_date:
                filtered.append(review)
        return filtered

    return all_reviews

def reply_to_review(creds, review_name, reply_text, account_name=None):
    """Reply to a review."""
    headers = {'Authorization': f'Bearer {_get_token(creds)}', 'Content-Type': 'application/json'}
    # review_name is typically accounts/.../locations/.../reviews/ID — normalise if needed
    if not review_name.startswith('accounts/') and account_name:
        review_name = f'{account_name}/{review_name}'
    r = _requests.put(f'{GMB_REVIEWS_BASE}/{review_name}/reply', headers=headers, json={'comment': reply_text})
    if not r.ok:
        print(f"Error replying to review: {r.status_code} {r.text}", file=sys.stderr)
        return None
    return r.json()

def analyze_sentiment(review):
    """Simple sentiment analysis based on star rating."""
    rating = review.get('starRating', 'ZERO')
    
    rating_map = {
        'FIVE': 5,
        'FOUR': 4,
        'THREE': 3,
        'TWO': 2,
        'ONE': 1,
        'ZERO': 0
    }
    
    stars = rating_map.get(rating, 0)
    
    if stars >= 4:
        return 'positive'
    elif stars == 3:
        return 'neutral'
    else:
        return 'negative'

def format_review(review, include_reply=True):
    """Format a review for display."""
    rating = review.get('starRating', 'ZERO')
    rating_map = {'FIVE': '⭐⭐⭐⭐⭐', 'FOUR': '⭐⭐⭐⭐', 'THREE': '⭐⭐⭐', 'TWO': '⭐⭐', 'ONE': '⭐', 'ZERO': ''}
    
    output = []
    output.append(f"Rating: {rating_map.get(rating, rating)}")
    output.append(f"Reviewer: {review.get('reviewer', {}).get('displayName', 'Anonymous')}")
    output.append(f"Date: {review.get('updateTime', 'Unknown')}")
    
    comment = review.get('comment', '')
    if comment:
        output.append(f"Comment: {comment}")
    
    if include_reply:
        reply = review.get('reviewReply', {})
        if reply:
            output.append(f"Reply: {reply.get('comment', '')}")
            output.append(f"Reply Date: {reply.get('updateTime', '')}")
    
    output.append(f"Review Name: {review.get('name', '')}")
    output.append("")
    
    return '\n'.join(output)

def generate_summary(reviews):
    """Generate summary statistics for reviews."""
    if not reviews:
        return "No reviews found in the specified time period."
    
    total = len(reviews)
    sentiments = {'positive': 0, 'neutral': 0, 'negative': 0}
    needs_reply = 0
    
    for review in reviews:
        sentiment = analyze_sentiment(review)
        sentiments[sentiment] += 1
        
        if not review.get('reviewReply'):
            needs_reply += 1
    
    summary = []
    summary.append(f"Total Reviews: {total}")
    summary.append(f"Positive: {sentiments['positive']} ({sentiments['positive']/total*100:.1f}%)")
    summary.append(f"Neutral: {sentiments['neutral']} ({sentiments['neutral']/total*100:.1f}%)")
    summary.append(f"Negative: {sentiments['negative']} ({sentiments['negative']/total*100:.1f}%)")
    summary.append(f"Needs Reply: {needs_reply}")
    
    return '\n'.join(summary)

def main():
    parser = argparse.ArgumentParser(description='Google My Business Reviews Manager')
    parser.add_argument('action', choices=['list-accounts', 'list-locations', 'list-reviews', 'reply', 'summary', 'rating'])
    parser.add_argument('--account', help='Account name (e.g., accounts/123456)')
    parser.add_argument('--location', help='Location name (e.g., accounts/123456/locations/789)')
    parser.add_argument('--review', help='Review name for reply action')
    parser.add_argument('--reply-text', help='Reply text for reply action')
    parser.add_argument('--days', type=int, default=7, help='Days back to fetch reviews (default: 7)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Get credentials
    creds = get_credentials()

    # Execute action
    if args.action == 'list-accounts':
        accounts = list_accounts(creds)
        if args.json:
            print(json.dumps(accounts, indent=2))
        else:
            for account in accounts:
                print(f"{account['name']} - {account.get('accountName', 'N/A')}")

    elif args.action == 'list-locations':
        if not args.account:
            print("ERROR: --account required", file=sys.stderr)
            sys.exit(1)

        locations = list_locations(creds, args.account)
        if args.json:
            print(json.dumps(locations, indent=2))
        else:
            for location in locations:
                print(f"{location['name']} - {location.get('title', location.get('locationName', 'N/A'))}")

    elif args.action == 'list-reviews':
        if not args.location:
            print("ERROR: --location required", file=sys.stderr)
            sys.exit(1)

        reviews = list_reviews(creds, args.location, args.days, account_name=args.account)
        if args.json:
            print(json.dumps(reviews, indent=2))
        else:
            for review in reviews:
                print(format_review(review))

    elif args.action == 'reply':
        if not args.review or not args.reply_text:
            print("ERROR: --review and --reply-text required", file=sys.stderr)
            sys.exit(1)

        response = reply_to_review(creds, args.review, args.reply_text)
        if response:
            print("Reply posted successfully!")
            if args.json:
                print(json.dumps(response, indent=2))

    elif args.action == 'rating':
        if not args.location:
            print("ERROR: --location required", file=sys.stderr)
            sys.exit(1)

        avg, total = get_location_rating(creds, args.location, account_name=args.account)
        if args.json:
            print(json.dumps({'averageRating': avg, 'totalReviewCount': total}))
        else:
            print(f"Average Rating: {avg} ({total} total reviews)")

    elif args.action == 'summary':
        if not args.location:
            print("ERROR: --location required", file=sys.stderr)
            sys.exit(1)

        avg, total = get_location_rating(creds, args.location, account_name=args.account)
        if avg is not None:
            print(f"Overall Rating: {avg}/5.0 ({total} total reviews)")
        reviews = list_reviews(creds, args.location, args.days, account_name=args.account)
        print(generate_summary(reviews))

        # Show negative reviews
        negative_reviews = [r for r in reviews if analyze_sentiment(r) == 'negative']
        if negative_reviews:
            print("\n=== NEGATIVE REVIEWS ===")
            for review in negative_reviews:
                print(format_review(review))

if __name__ == '__main__':
    main()
