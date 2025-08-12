import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import re
import os

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
        
        # Extract sales information
        sales = extract_sales_info(soup)
        print(f"Found {len(sales)} estate sales")
        
        # Organize and format the results
        organized_sales = organize_sales_by_weekend(sales)
        
        # Create email content
        email_content = create_email_content(organized_sales)
        
        # Send email
        send_email(email_content)
        
        print("Estate sales email sent successfully!")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        send_error_email(str(e))

def extract_sales_info(soup):
    """Extract individual sale information from the parsed HTML"""
    sales = []
    
    # Look for sale links - EstateSales.NET uses specific URL patterns
    sale_links = soup.find_all('a', href=re.compile(r'/TX/Austin/\d+/\d+'))
    
    print(f"Found {len(sale_links)} sale links")
    
    processed_urls = set()  # Avoid duplicates
    
    for link in sale_links:
        try:
            # Get the sale URL
            sale_url = link.get('href')
            if sale_url in processed_urls:
                continue
            processed_urls.add(sale_url)
            
            # Find the container that has the sale information
            sale_container = link.find_parent(['div', 'article', 'section'])
            if not sale_container:
                sale_container = link
            
            # Extract sale information
            title = extract_sale_title(sale_container, link)
            address = extract_sale_address(sale_container)
            dates = extract_sale_dates(sale_container)
            
            sale = {
                'title': title,
                'address': address,
                'dates': dates,
                'link': f"https://www.estatesales.net{sale_url}"
            }
            
            sales.append(sale)
            
            # Limit to prevent too many results
            if len(sales) >= 25:
                break
                
        except Exception as e:
            print(f"Error processing sale link: {str(e)}")
            continue
    
    return sales

def extract_sale_title(container, link):
    """Extract the title of the estate sale"""
    # Try different methods to find the title
    
    # Method 1: Look for heading tags
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        heading = container.find(tag)
        if heading and heading.get_text(strip=True):
            title = heading.get_text(strip=True)
            if len(title) > 5 and len(title) < 150:
                return title
    
    # Method 2: Look for title attribute
    if link.get('title'):
        title = link.get('title').strip()
        if len(title) > 5:
            return title
    
    # Method 3: Look for text content with good length
    text_content = container.get_text(strip=True)
    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
    
    for line in lines:
        if 10 < len(line) < 100 and not line.startswith('http') and 'TX' not in line:
            return line
    
    return "Estate Sale"

def extract_sale_address(container):
    """Extract the address of the estate sale"""
    text = container.get_text()
    
    # Look for Texas address patterns
    address_patterns = [
        r'\d+[^,\n]*,\s*[A-Za-z\s]+,\s*TX\s*\d*',
        r'Austin,\s*TX\s*\d*',
        r'TX\s*\d{5}'
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            address = match.group().strip()
            if len(address) > 5:
                return address
    
    return "Austin, TX (see website for full address)"

def extract_sale_dates(container):
    """Extract the dates of the estate sale"""
    text = container.get_text()
    
    # Look for date patterns
    date_patterns = [
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:\s*,\s*\d{4})?',
        r'\d{1,2}/\d{1,2}(?:/\d{2,4})?',
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
    ]
    
    found_dates = []
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = ' '.join(match)
            if match not in found_dates:
                found_dates.append(match)
    
    if found_dates:
        return ', '.join(found_dates[:4])  # Limit to first 4 dates
    
    return "See website for dates"

def organize_sales_by_weekend(sales):
    """Organize sales into weekend buckets"""
    today = datetime.now()
    
    # Calculate this weekend and next weekend date ranges
    days_until_thursday = (3 - today.weekday()) % 7  # Thursday is 3
    if days_until_thursday == 0 and today.weekday() > 3:
        days_until_thursday = 7
    
    this_weekend_start = today + timedelta(days=days_until_thursday)
    next_weekend_start = this_weekend_start + timedelta(days=7)
    
    this_weekend_days = set()
    next_weekend_days = set()
    
    # This weekend: Thursday through Sunday
    for i in range(4):  # Thu, Fri, Sat, Sun
        day = this_weekend_start + timedelta(days=i)
        this_weekend_days.add(day.day)
    
    # Next weekend: Thursday through Sunday
    for i in range(4):
        day = next_weekend_start + timedelta(days=i)
        next_weekend_days.add(day.day)
    
    print(f"This weekend target days: {sorted(this_weekend_days)}")
    print(f"Next weekend target days: {sorted(next_weekend_days)}")
    
    this_weekend = []
    next_weekend = []
    other_sales = []
    
    for sale in sales:
        dates_text = sale['dates'].lower()
        
        # Extract day numbers from the date string
        day_numbers = [int(x) for x in re.findall(r'\b(\d{1,2})\b', dates_text) if 1 <= int(x) <= 31]
        
        # Check if any day matches our weekend periods
        is_this_weekend = any(day in this_weekend_days for day in day_numbers)
        is_next_weekend = any(day in next_weekend_days for day in day_numbers)
        
        if is_this_weekend and not is_next_weekend:
            this_weekend.append(sale)
        elif is_next_weekend and not is_this_weekend:
            next_weekend.append(sale)
        else:
            other_sales.append(sale)
    
    return {
        'this_weekend': this_weekend,
        'next_weekend': next_weekend,
        'other': other_sales
    }

def create_email_content(organized_sales):
    """Create the formatted email content"""
    content = "AUSTIN ESTATE SALES - WEEKLY UPDATE\n"
    content += "===================================\n"
    content += f"Generated: {datetime.now().strftime('%B %d, %Y')}\n\n"
    
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
        
        for i, sale in enumerate(organized_sales['other'][:10], 1):  # Limit to 10
            content += f"{i}. {sale['title']}\n"
            content += f"   Address: {sale['address']}\n"
            content += f"   Dates: {sale['dates']}\n"
            content += f"   Link: {sale['link']}\n\n"
    
    content += "\nHappy treasure hunting!\n"
    content += "- Austin Estate Sales Tracker"
    
    return content

def send_email(content):
    """Send the email using Gmail SMTP"""
    # Get email credentials from environment variables
    sender_email = os.environ.get('GMAIL_USER')
    sender_password = os.environ.get('GMAIL_APP_PASSWORD')
    recipient_email = os.environ.get('RECIPIENT_EMAIL')
    
    if not all([sender_email, sender_password, recipient_email]):
        print("Email credentials not found in environment variables")
        return
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"Austin Estate Sales - {datetime.now().strftime('%B %d, %Y')}"
        
        # Add body to email
        msg.attach(MIMEText(content, 'plain'))
        
        # Gmail SMTP configuration
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Enable security
        server.login(sender_email, sender_password)
        
        # Send email
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
