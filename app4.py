import streamlit as st
import json
import os
import re
import smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Set Streamlit Page Configuration - Clean mobile vertical stack
st.set_page_config(
    page_title="LensFlow Mobile",
    page_icon="📸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

BOOKINGS_JSON = "bookings.json"
STAFF_JSON = "staff.json"
SETTINGS_JSON = "settings.json"

EVENT_TYPES = [
    "Photography", "Videography", "Photography + Videography", 
    "Wedding", "Pre Wedding", "Birthday", "Corporate", 
    "Product Shoot", "Drone", "Other"
]

def init_storage():
    """Initializes JSON data storage files using Python core dictionaries."""
    if not os.path.exists(SETTINGS_JSON):
        default_settings = {
            "business_name": "My Photography Studio",
            "owner_name": "Studio Owner",
            "owner_email": "owner@example.com",
            "smtp_email": "smtp@example.com",
            "smtp_password": "",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "business_phone": "1234567890",
            "business_address": "123 Studio Lane"
        }
        with open(SETTINGS_JSON, "w") as f:
            json.dump(default_settings, f, indent=4)

    if not os.path.exists(BOOKINGS_JSON):
        with open(BOOKINGS_JSON, "w") as f:
            json.dump([], f)
        
    if not os.path.exists(STAFF_JSON):
        with open(STAFF_JSON, "w") as f:
            json.dump([], f)

init_storage()

def load_json_file(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def send_html_email(to_email, subject, html_body):
    settings = load_json_file(SETTINGS_JSON)
    if isinstance(settings, list) or not settings.get("smtp_email") or not settings.get("smtp_password"):
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings['business_name']} <{settings['smtp_email']}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(settings["smtp_server"], int(settings["smtp_port"])) as server:
            server.starttls()
            server.login(settings["smtp_email"], settings["smtp_password"])
            server.sendmail(settings["smtp_email"], to_email, msg.as_string())
        return True
    except Exception:
        return False

def dispatch_booking_emails(booking):
    settings = load_json_file(SETTINGS_JSON)
    client_html = f"<html><body><h2>Booking Confirmed! 🎉</h2><p>ID: {booking['Booking ID']}<br>Date: {booking['Booking Date']}</p></body></html>"
    send_html_email(booking['Email'], f"Booking Confirmed - ID: {booking['Booking ID']}", client_html)

# Clean Mobile Layout Interface
st.title("📸 LensFlow Mobile")
page = st.selectbox("Go To Section", [
    "📊 Dashboard", 
    "➕ New Booking", 
    "🔍 Search & Edit", 
    "📅 Work List",
    "⚙️ Settings"
])

st.markdown("---")

if page == "📊 Dashboard":
    bookings = load_json_file(BOOKINGS_JSON)
    
    if bookings:
        active_bookings = [b for b in bookings if b.get("Status") != "Cancelled"]
        total_rev = sum(float(b.get("Amount", 0)) for b in active_bookings)
        pending_amt = sum(float(b.get("Remaining", 0)) for b in active_bookings)
        
        st.metric("Gross Revenue", f"${total_rev:,.2f}")
        st.metric("Outstanding Balance", f"${pending_amt:,.2f}")
        st.metric("Active Bookings", len(active_bookings))
        
        # Count event types manually to remove dependency chart requirements
        st.subheader("Event Distribution Breakdown")
        counts = {}
        for b in active_bookings:
            etype = b.get("Event Type", "Other")
            counts[etype] = counts.get(etype, 0) + 1
        
        for k, v in counts.items():
            st.markdown(f"*{k}*: **{v} shoots**")
    else:
        st.info("No bookings recorded yet.")

elif page == "➕ New Booking":
    st.subheader("Add Booking Ledger")
    bookings = load_json_file(BOOKINGS_JSON)
    staff = load_json_file(STAFF_JSON)
    
    next_id = f"LF-{1001 + len(bookings)}"
    
    with st.form("mobile_booking_form"):
        client_name = st.text_input("Client Name *")
        client_phone = st.text_input("Phone *")
        client_email = st.text_input("Email *")
        client_address = st.text_input("Address *")
        event_type = st.selectbox("Event Type", EVENT_TYPES)
        event_date = st.date_input("Event Date", min_value=date.today())
        shoot_time = st.text_input("Call Time", "10:00 AM")
        venue = st.text_input("Venue *")
        maps_link = st.text_input("Google Maps URL")
        
        staff_options = [s["Staff Name"] for s in staff] if staff else []
        staff_options.append("None / Unassigned")
        assigned_staff = st.selectbox("Assign Staff", staff_options)
        
        amount = st.number_input("Total Amount ($)", min_value=0.0)
        advance = st.number_input("Advance Paid ($)", min_value=0.0)
        payment_status = st.selectbox("Payment Status", ["Pending", "Partial", "Paid"])
        notes = st.text_area("Notes")
        
        submit = st.form_submit_button("Save Booking Ledger")
        
        if submit:
            if not client_name or not client_phone or not client_email or not venue:
                st.error("Please fill all mandatory fields (*)")
            elif not validate_email(client_email):
                st.error("Invalid email address format.")
            else:
                new_booking = {
                    "Booking ID": next_id,
                    "Booking Date": str(event_date),
                    "Client Name": client_name.strip(),
                    "Phone": client_phone.strip(),
                    "Email": client_email.strip(),
                    "Address": client_address.strip(),
                    "Event Type": event_type,
                    "Venue": venue.strip(),
                    "Time": shoot_time.strip(),
                    "Assigned Staff": assigned_staff,
                    "Amount": amount,
                    "Advance": advance,
                    "Remaining": amount - advance,
                    "Payment Status": payment_status,
                    "Status": "Active",
                    "Notes": f"{notes} | Maps: {maps_link}",
                    "Created Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                bookings.append(new_booking)
                save_json_file(BOOKINGS_JSON, bookings)
                st.success(f"Booking Saved! ID: {next_id}")
                dispatch_booking_emails(new_booking)

elif page == "🔍 Search & Edit":
    bookings = load_json_file(BOOKINGS_JSON)
    if not bookings:
        st.info("No data available.")
    else:
        search = st.text_input("Search by Name or ID")
        filtered_bookings = bookings
        
        if search:
            filtered_bookings = [
                b for b in bookings if search.lower() in b["Client Name"].lower() or search.lower() in b["Booking ID"].lower()
            ]
        
        for b in filtered_bookings:
            st.markdown(f"**{b['Booking ID']}** - {b['Client Name']} ({b['Booking Date']}) -> *{b['Status']}*")
            
        selected_id = st.selectbox("Select ID to Edit/Delete", ["Choose..."] + [b["Booking ID"] for b in filtered_bookings])
        if selected_id != "Choose...":
            idx = next(i for i, b in enumerate(bookings) if b["Booking ID"] == selected_id)
            target = bookings[idx]
            
            edit_status = st.selectbox("Job Status", ["Active", "Completed", "Cancelled"], index=["Active", "Completed", "Cancelled"].index(target["Status"]))
            edit_pay = st.selectbox("Payment Stage", ["Pending", "Partial", "Paid"], index=["Pending", "Partial", "Paid"].index(target["Payment Status"]))
            
            if st.button("Update Record"):
                bookings[idx]["Status"] = edit_status
                bookings[idx]["Payment Status"] = edit_pay
                save_json_file(BOOKINGS_JSON, bookings)
                st.success("Record updated!")
                st.rerun()
                
            if st.button("Delete Permanently"):
                bookings.pop(idx)
                save_json_file(BOOKINGS_JSON, bookings)
                st.warning("Record deleted.")
                st.rerun()

elif page == "📅 Work List":
    bookings = load_json_file(BOOKINGS_JSON)
    if not bookings:
        st.info("No scheduled records.")
    else:
        # Sort manually by date string
        bookings.sort(key=lambda x: x["Booking Date"])
        
        # Group entries by unique date manually
        date_groups = {}
        for b in bookings:
            d = b["Booking Date"]
            if d not in date_groups:
                date_groups[d] = []
            date_groups[d].append(b)
            
        for unique_date, group in date_groups.items():
            st.markdown(f"#### 📅 {unique_date}")
            for row in group:
                st.markdown(f"**{row['Time']}** - {row['Event Type']} for *{row['Client Name']}* at `{row['Venue']}` ({row['Status']})")
            st.markdown("---")

elif page == "⚙️ Settings":
    current_settings = load_json_file(SETTINGS_JSON)
    if isinstance(current_settings, list):
        current_settings = {}
        
    with st.form("settings_form"):
        biz_name = st.text_input("Studio Name", value=current_settings.get("business_name", ""))
        owner_em = st.text_input("Owner Email", value=current_settings.get("owner_email", ""))
        smtp_e = st.text_input("SMTP Email", value=current_settings.get("smtp_email", ""))
        smtp_p = st.text_input("SMTP Password", value=current_settings.get("smtp_password", ""), type="password")
        
        if st.form_submit_button("Save Configurations"):
            current_settings.update({
                "business_name": biz_name,
                "owner_email": owner_em,
                "smtp_email": smtp_e,
                "smtp_password": smtp_p
            })
            save_json_file(SETTINGS_JSON, current_settings)
            st.success("Settings saved locally.")
