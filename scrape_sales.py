import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import re
import os
import pytz

def scrape_estate_sales():
    """Scrape estate sales from EstateSales.NET for Austin, TX"""
    print("Starting estate sale scraper...")
    
    # URL for Austin estate sales
    url = "https://www.estatesales.net/TX/Austin"
    
    try:
        # Make request with headers to look like a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print(f"Fetching data from: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        print(f"Successfully fetched {len(response.text)} characters")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract sales information with improved method
        sales = extract_sales_info_improved(soup)
        print(f"Found {len(sales)} estate sales")
        
        # Debug: Print first few sales
        for i, sale in enumerate(sales[:3]):
            print(f"Sale {i+1}: {sale['title'][:50]}... | Dates: {sale['dates']}")
        
        # Organize and format the results with fixed weekend logic
        organized_sales = organize_sales_by_weekend_fixed(sales)
        
        # Create email content
        email_content = create_email_content_improved(organized_sales)
        
        # Send email
        send_email(email_content)
        
        print("Estate sales email sent successfully!")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        send_error_email(str(e))

def extract_sales_info_improved(soup):
    """Extract individual sale information with better parsing"""
    sales = []
    
    # Method 1: Look for sale containers more broadly
    sale_containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'sale|listing|item'))
    print(f"Found {len(sale_containers)} potential sale containers using class search")
    
    # Method 2: Look for all links to sales
    sale_links = soup.find_all('a', href=re.compile(r'/TX/Austin/\d+/\d+'))
    print(f"Found {len(sale_links)} sale links")
    
    # Method 3: Text-based extraction - look for sales in the HTML text
    sales_from_text = extract_from_html_text(soup)
    print(f"Found {len(sales_from_text)} sales from text extraction")
    
    # Combine all methods
    processed_urls = set()
    
    # Process sale links (most reliable)
    for link in sale_links[:30]:  # Increased limit
        try:
            sale_url = link.get('href')
            if sale_url in processed_urls:
                continue
            processed_urls.add(sale_url)
            
            # Get surrounding content for this link
            container = find_sale_container(link)
            
            title = extract_sale_title_improved(container, link)
            address = extract_sale_address_improved(container)
            dates = extract_sale_dates_improved(container)
            
            sale = {
                'title': title,
                'address': address,
                'dates': dates,
                'link': f"https://www.estatesales.net{sale_url}"
            }
            
            sales.append(sale)
            
        except Exception as e:
            print(f"Error processing sale link: {str(e)}")
            continue
    
    # Add sales from text extraction if we don't have many
    if len(sales) < 10:
        sales.extend(sales_from_text[:10])
    
    return sales[:25]  # Return up to 25 sales

def find_sale_container(link):
    """Find the container that holds the sale information"""
    # Try to find the parent container that has the sale info
    container = link
    
    # Go up the DOM tree to find a good container
    for i in range(5):  # Try up to 5 levels up
        if container.parent:
            container = container.parent
            # Stop if we find a container with good content
            text_content = container.get_text()
            if len(text_content) > 100 and ('Austin' in text_content or 'TX' in text_content):
                break
    
    return container

def extract_sale_title_improved(container, link):
    """Extract title with multiple strategies"""
    # Strategy 1: Heading tags
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        heading = container.find(tag)
        if heading and heading.get_text(strip=True):
            title = heading.get_text(strip=True)
            if 5 < len(title) < 150 and not title.lower().startswith('http'):
                return clean_text(title)
    
    # Strategy 2: Title attribute
    if link.get('title'):
        title = link.get('title').strip()
        if len(title) > 5:
            return clean_text(title)
    
    # Strategy 3: Strong/bold text
    strong_tags = container.find_all(['strong', 'b'])
    for tag in strong_tags:
        text = tag.get_text(strip=True)
        if 10 < len(text) < 100:
            return clean_text(text)
    
    # Strategy 4: Look for descriptive text
    text_content = container.get_text()
    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
    
    for line in lines:
        # Skip lines that are clearly not titles
        if (10 < len(line) < 100 and 
            not line.startswith('http') and 
            not re.match(r'^\d+$', line) and
            not line.lower().startswith('austin, tx')):
            return clean_text(line)
    
    return "Estate Sale"

def extract_sale_address_improved(container):
    """Extract address with better patterns"""
    text = container.get_text()
    
    # Address patterns for Austin area
    patterns = [
        r'\d+[^,\n]*(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|blvd|boulevard|circle|cir|court|ct|place|pl)[^,\n]*,\s*[A-Za-z\s]+,\s*TX\s*\d*',
        r'\d+[^,\n]*,\s*Austin,\s*TX\s*\d*',
        r'\d+[^,\n]*,\s*[A-Za-z\s]+,\s*TX\s*\d{5}',
        r'Austin,\s*TX\s*\d{5}',
        r'TX\s*\d{5}'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            address = match.group().strip()
            if len(address) > 8:
                return clean_text(address)
    
    return "Austin, TX (see website for full address)"

def extract_sale_dates_improved(container):
    """Extract dates with comprehensive patterns"""
    text = container.get_text()
    
    # Multiple date patterns
    patterns = [
        # "Aug 14, 15, 16" or "August 14-16"
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:\s*[-,]\s*\d{1,2})*(?:\s*[-,]\s*\d{1,2})*',
        # "8/14, 8/15, 8/16" or "8/14-8/16"
        r'\d{1,2}/\d{1,2}(?:\s*[-,]\s*\d{1,2}/\d{1,2})*',
        # Day names
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s*[-,]\s*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))*',
        # "14th, 15th, 16th"
        r'\d{1,2}(?:st|nd|rd|th)(?:\s*[-,]\s*\d{1,2}(?:st|nd|rd|th))*'
    ]
    
    found_dates = []
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                # Handle tuple results from groups
                date_str = ' '.join([m for m in match if m])
            else:
                date_str = match
            
            if date_str and date_str not in found_dates:
                found_dates.append(date_str)
    
    if found_dates:
        # Return the first few unique dates
        return ', '.join(found_dates[:5])
    
    return "See website for dates"

def extract_from_html_text(soup):
    """Extract sales by parsing HTML text patterns"""
    sales = []
    
    # Get all text and look for sale patterns
    text = soup.get_text()
    
    # Look for URLs in the text
    url_pattern = r'/TX/Austin/(\d+)/(\d+)'
    url_matches = re.findall(url_pattern, text)
    
    for match in url_matches[:10]:
        sale_id = match[1]
        sale_url = f"/TX/Austin/{match[0]}/{match[1]}"
        
        sales.append({
            'title': f"Estate Sale #{sale_id}",
            'address': "Austin, TX (see website)",
            'dates': "Check website for dates",
            'link': f"https://www.estatesales.net{sale_url}"
        })
    
    return sales

def organize_sales_by_weekend_fixed(sales):
    """Fixed weekend organization with proper timezone handling"""
    # Use Central Time Zone
    central_tz = pytz.timezone('US/Central')
    utc_now = datetime.utcnow()
    central_now = utc_now.replace(tzinfo=pytz.UTC).astimezone(central_tz)
    
    print(f"Current Central Time: {central_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Current day of week: {central_now.strftime('%A')} (weekday: {central_now.weekday()})")
    
    # Calculate this weekend (Thursday-Sunday)
    current_weekday = central_now.weekday()  # Monday=0, Sunday=6
    
    # Days until Thursday (weekday 3)
    if current_weekday <= 3:  # Monday through Thursday
        days_to_thursday = 3 - current_weekday
    else:  # Friday, Saturday, Sunday
        days_to_thursday = 7 - current_weekday + 3  # Next Thursday
    
    this_thursday = central_now + timedelta(days=days_to_thursday)
    next_thursday = this_thursday + timedelta(days=7)
    
    # This weekend: Thursday through Sunday
    this_weekend_days = []
    for i in range(4):  # Thu, Fri, Sat, Sun
        day = this_thursday + timedelta(days=i)
        this_weekend_days.append(day.day)
    
    # Next weekend: Thursday through Sunday  
    next_weekend_days = []
    for i in range(4):
        day = next_thursday + timedelta(days=i)
        next_weekend_days.append(day.day)
    
    print(f"This weekend dates: {this_thursday.strftime('%A %b %d')} - {(this_thursday + timedelta(days=3)).strftime('%A %b %d')}")
    print(f"This weekend target days: {this_weekend_days}")
    print(f"Next weekend target days: {next_weekend_days}")
    
    this_weekend = []
    next_weekend = []
    other_sales = []
    
    for sale in sales:
        dates_text = sale['dates'].lower()
        print(f"Processing sale: {sale['title'][:30]}... | Dates: {dates_text}")
        
        # Extract day numbers from the date string
        day_numbers = [int(x) for x in re.findall(r'\b(\d{1,2})\b', dates_text) if 1 <= int(x) <= 31]
        print(f"  Found day numbers: {day_numbers}")
        
        # Check if any day matches our weekend periods
        is_this_weekend = any(day in this_weekend_days for day in day_numbers)
        is_next_weekend = any(day in next_weekend_days for day in day_numbers)
        
        if is_this_weekend and not is_next_weekend:
            this_weekend.append(sale)
            print(f"  -> Assigned to THIS WEEKEND")
        elif is_next_weekend and not is_this_weekend:
            next_weekend.append(sale)
            print(f"  -> Assigned to NEXT WEEKEND")
        else:
            other_sales.append(sale)
            print(f"  -> Assigned to OTHER")
    
    print(f"Final counts: This weekend: {len(this_weekend)}, Next weekend: {len(next_weekend)}, Other: {len(other_sales)}")
    
    return {
        'this_weekend': this_weekend,
        'next_weekend': next_weekend,
        'other': other_sales
    }

def create_email_content_improved(organized_sales):
    """Create email with better formatting and Central Time"""
    central_tz = pytz.timezone('US/Central')
    central_now = datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(central_tz)
    
    content = "AUSTIN ESTATE SALES - WEEKLY UPDATE\n"
    content += "===================================\n"
    content += f"Generated: {central_now.strftime('%B %d, %Y at %I:%M %p Central')}\n\n"
    
    # This Weekend Section
    content += "THIS WEEKEND (Thursday - Sunday)\n"
    content += "--------------------------------\n\n"
    
    if not organized_sales['this_weekend']:
        content += "No estate sales found for this weekend.\n\n"
    else:
        for i, sale in enumerate(organized_sales['this_weekend'], 1):
            content += f"{i}. {sale['title']}\n"
            content += f"   Address: {sale['address']}\n"
            content += f"   Dates: {sale['dates']}\n"
            content += f"   Link: {sale['link']}\n\n"
    
    # Next Weekend Section
    content += "NEXT WEEKEND (Thursday - Sunday)\n"
    content += "---------------------------------\n\n"
    
    if not organized_sales['next_weekend']:
        content += "No estate sales found for next weekend.\n\n"
    else:
        for i, sale in enumerate(organized_sales['next_weekend'], 1):
            content += f"{i}. {sale['title']}\n"
            content += f"   Address: {sale['address']}\n"
            content += f"   Dates: {sale['dates']}\n"
            content += f"   Link: {sale['link']}\n\n"
    
    # Other Sales
    if organized_sales['other']:
        content += "OTHER UPCOMING SALES\n"
        content += "--------------------\n\n"
        
        for i, sale in enumerate(organized_sales['other'][:15], 1):
            content += f"{i}. {sale['title']}\n"
            content += f"   Address: {sale['address']}\n"
            content += f"   Dates: {sale['dates']}\n"
            content += f"   Link: {sale['link']}\n\n"
    
    content += f"\nHappy treasure hunting!\n"
    content += f"- Austin Estate Sales Tracker (Last updated: {central_now.strftime('%m/%d/%Y %I:%M %p CT')})"
    
    return content

def clean_text(text):
    """Clean and normalize text"""
    # Remove extra whitespace and clean up
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove HTML entities
    text = text.replace('&amp;', '&').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
    return text

def send_email(content):
    """Send the email using Gmail SMTP"""
    sender_email = os.environ.get('GMAIL_USER')
    sender_password = os.environ.get('GMAIL_APP_PASSWORD')
    recipient_email = os.environ.get('RECIPIENT_EMAIL')
    
    if not all([sender_email, sender_password, recipient_email]):
        print("Email credentials not found in environment variables")
        return
    
    try:
        # Use Central Time for email subject
        central_tz = pytz.timezone('US/Central')
        central_now = datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(central_tz)
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"Austin Estate Sales - {central_now.strftime('%B %d, %Y')}"
        
        msg.attach(MIMEText(content, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print("Email sent successfully!")
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

def send_error_email(error_message):
    """Send an error notification email"""
    try:
        sender_email = os.environ.get('GMAIL_USER')
        sender_password = os.environ.get('GMAIL_APP_PASSWORD')
        recipient_email = os.environ.get('RECIPIENT_EMAIL')
        
        if not all([sender_email, sender_password, recipient_email]):
            return
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = "Austin Estate Sales - Error Notification"
        
        content = f"An error occurred while running the estate sales scraper:\n\n{error_message}"
        msg.attach(MIMEText(content, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        
    except Exception as e:
        print(f"Failed to send error email: {str(e)}")

if __name__ == "__main__":
    scrape_estate_sales()
