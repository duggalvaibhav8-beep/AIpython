import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from typing import Optional

class EmailService:
    """Email service for sending notifications"""
    
    def __init__(self):
        # Email configuration - Use environment variables in production
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL", "smartbookingai@example.com")
        self.sender_password = os.getenv("SENDER_PASSWORD", "")
        self.sender_name = os.getenv("SENDER_NAME", "SmartBookingAI")
        
    def send_email(
        self, 
        recipient_email: str, 
        subject: str, 
        html_body: str,
        plain_body: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Send an email
        Returns: (success: bool, error_message: Optional[str])
        """
        
        # For development/testing: Just log instead of actually sending
        if not self.sender_password or self.sender_password == "":
            print(f"""
            ====== EMAIL SIMULATION ======
            To: {recipient_email}
            Subject: {subject}
            
            {html_body[:200]}...
            ==============================
            """)
            return True, None
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.sender_name} <{self.sender_email}>"
            message["To"] = recipient_email
            
            # Add plain text version
            if plain_body:
                part1 = MIMEText(plain_body, "plain")
                message.attach(part1)
            
            # Add HTML version
            part2 = MIMEText(html_body, "html")
            message.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_email, message.as_string())
            
            print(f"✓ Email sent successfully to {recipient_email}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            print(f"✗ {error_msg}")
            return False, error_msg