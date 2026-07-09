import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import re
import smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import plotly.express as px
from apscheduler.schedulers.background import BackgroundScheduler

# ==========================================
# CONSTANTS & INITIALIZATION
# ==========================================
BOOKINGS_XLSX = "bookings.xlsx"
BOOKINGS_CSV = "bookings.csv"
STAFF_XLSX = "staff.xlsx"
SETTINGS_JSON = "settings.json"

EVENT_TYPES = [
    "Photography", "Videography", "Photography + Videography", 
    "Wedding", "Pre Wedding", "Birthday", "Corporate", 
    "Product Shoot", "Drone", "Other"
]

STAFF_ROLES = ["Photographer", "Videographer", "Editor", "Assistant", "Driver", "Other"]

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="LensFlow | Photography Business Management",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# ATOMIC CORE FILE OPERATIONS (AUTO-SAVE/LOAD)
# ==========================================
def init_storage():
    """Ensures all backing database-like files exist with a consistent schema."""
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

    booking_cols = [
        "Booking ID", "Booking Date", "Client Name", "Phone", "Email", 
        "Address", "Event Type", "Venue", "Time", "Assigned Staff", 
        "Amount", "Advance", "Remaining", "Payment Status", "Status", "Notes", "Created Time"
    ]
    if not os.path.exists(BOOKINGS_XLSX):
        df = pd.DataFrame(columns=booking_cols)
        df.to_excel(BOOKINGS_XLSX, index=False)
        df.to_csv(BOOKINGS_CSV, index=False)
        
    staff_cols = ["Staff Name", "Staff Phone", "Staff Email", "Role"]
    if not os.path.exists(STAFF_XLSX):
        df_staff = pd.DataFrame(columns=staff_cols)
        df_staff.to_excel(STAFF_XLSX, index=False)

init_storage()

def load_settings():
    with open(SETTINGS_JSON, "r") as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_JSON, "w") as f:
        json.dump(data, f, indent=4)

def load_bookings():
    try:
        df = pd.read_excel(BOOKINGS_XLSX, dtype={"Booking ID": str, "Phone": str})
        df["Booking Date"] = pd.to_datetime(df["Booking Date"]).dt.date
        df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce').fillna(0.0)
        df["Advance"] = pd.to_numeric(df["Advance"], errors='coerce').fillna(0.0)
        df["Remaining"] = pd.to_numeric(df["Remaining"], errors='coerce').fillna(0.0)
        return df
    except Exception:
        return pd.read_csv(BOOKINGS_CSV, dtype={"Booking ID": str, "Phone": str})

def save_bookings(df):
    df.to_excel(BOOKINGS_XLSX, index=False)
    df.to_csv(BOOKINGS_CSV, index=False)

def load_staff():
    return pd.read_excel(STAFF_XLSX, dtype={"Staff Phone": str})

def save_staff(df):
    df.to_excel(STAFF_XLSX, index=False)

# ==========================================
# VALIDATION UTILITIES
# ==========================================
def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def validate_phone(phone):
    return re.match(r"^\+?1?\d{9,15}$", phone) is not None

# ==========================================
# EMAIL ENGINE & AUTOMATION
# ==========================================
def send_html_email(to_email, subject, html_body):
    settings = load_settings()
    if not settings["smtp_email"] or not settings["smtp_password"]:
        return False, "SMTP configuration missing or incomplete in Settings."
    
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
        return True, "Success"
    except Exception as e:
        return False, str(e)

def dispatch_booking_emails(booking_data):
    settings = load_settings()
    
    client_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #4CAF50;">Booking Confirmed! 🎉</h2>
        <p>Dear {booking_data['Client Name']},</p>
        <p>Thank you for choosing <strong>{settings['business_name']}</strong>! Your booking is successfully secured.</p>
        <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Booking ID:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{booking_data['Booking ID']}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{booking_data['Booking Date']}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Time:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{booking_data['Time']}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Venue:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{booking_data['Venue']}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Notes / Maps:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{booking_data['Notes']}</td></tr>
        </table>
        <br><p>Best regards,<br>{settings['owner_name']}<br>{settings['business_phone']}</p>
    </body>
    </html>
    """
    send_html_email(booking_data['Email'], f"Booking Confirmed - ID: {booking_data['Booking ID']}", client_html)

    staff_df = load_staff()
    matched_staff = staff_df[staff_df["Staff Name"] == booking_data["Assigned Staff"]]
    if not matched_staff.empty:
        staff_email = matched_staff.iloc[0]["Staff Email"]
        staff_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #2196F3;">New Assignment Documented</h2>
            <p>Hello {booking_data['Assigned Staff']}, you have been assigned to a new shoot profile:</p>
            <ul>
                <li><strong>Client Profile:</strong> {booking_data['Client Name']}</li>
                <li><strong>Event Type:</strong> {booking_data['Event Type']}</li>
                <li><strong>Schedule Time:</strong> {booking_data['Booking Date']} @ {booking_data['Time']}</li>
                <li><strong>Venue Address:</strong> {booking_data['Address']} / {booking_data['Venue']}</li>
            </ul>
            <p><strong>Notes:</strong> {booking_data['Notes']}</p>
        </body>
        </html>
        """
        send_html_email(staff_email, f"Job Assignment Alert - Date: {booking_data['Booking Date']}", staff_html)

    owner_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #9C27B0;">Admin Copy: New Booking Order Added</h2>
        <pre>{json.dumps(booking_data, indent=4, default=str)}</pre>
    </body>
    </html>
    """
    send_html_email(settings["owner_email"], f"System Notification: Booking Creation [{booking_data['Booking ID']}]", owner_html)

def check_and_send_reminders():
    bookings_df = load_bookings()
    settings = load_settings()
    tomorrow = date.today() + timedelta(days=1)
    
    tomorrow_bookings = bookings_df[
        (pd.to_datetime(bookings_df["Booking Date"]).dt.date == tomorrow) & 
        (bookings_df["Status"] != "Cancelled")
    ]
    
    for _, row in tomorrow_bookings.iterrows():
        reminder_body = f"""
        <html>
        <body>
            <h3>⏰ Upcoming Assignment Reminder (Tomorrow)</h3>
            <p><strong>Event:</strong> {row['Event Type']} for {row['Client Name']}</p>
            <p><strong>Time Slot:</strong> {row['Time']}</p>
            <p><strong>Venue Address:</strong> {row['Address']} - {row['Venue']}</p>
        </body>
        </html>
        """
        send_html_email(row['Email'], "Reminder: Your Scheduled Event Tomorrow", reminder_body)
        send_html_email(settings["owner_email"], f"Admin Alert: Tomorrow's Schedule Tracking - ID {row['Booking ID']}", reminder_body)
        
        staff_df = load_staff()
        matched_staff = staff_df[staff_df["Staff Name"] == row["Assigned Staff"]]
        if not matched_staff.empty:
            send_html_email(matched_staff.iloc[0]["Staff Email"], "Reminder: Call Time Tomorrow", reminder_body)

scheduler = BackgroundScheduler()
if not scheduler.get_jobs():
    scheduler.add_job(check_and_send_reminders, 'cron', hour=8, minute=0)
    scheduler.start()

# ==========================================
# APP APPLICATION LAYOUT & ROUTING NAVIGATION
# ==========================================
st.sidebar.title("📸 LensFlow System")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate Workspace", [
    "📊 Master Dashboard", 
    "➕ New Booking Entry", 
    "🔍 Browse & Manage Bookings", 
    "📅 Studio Work Calendar",
    "⚙️ Settings & Configuration"
])

if page == "📊 Master Dashboard":
    st.title("📊 Production Analytics Dashboard")
    df = load_bookings()
    staff_df = load_staff()
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    df_active = df[df["Status"] != "Cancelled"] if not df.empty else pd.DataFrame(columns=df.columns)
    today_count = len(df_active[pd.to_datetime(df_active["Booking Date"]).dt.date == today]) if not df_active.empty else 0
    tomorrow_count = len(df_active[pd.to_datetime(df_active["Booking Date"]).dt.date == tomorrow]) if not df_active.empty else 0
    upcoming_count = len(df_active[pd.to_datetime(df_active["Booking Date"]).dt.date > today]) if not df_active.empty else 0
    
    total_rev = df_active["Amount"].sum() if not df_active.empty else 0.0
    pending_amt = df_active["Remaining"].sum() if not df_active.empty else 0.0
    completed_shoots = len(df[df["Status"] == "Completed"]) if not df.empty else 0
    cancelled_count = len(df[df["Status"] == "Cancelled"]) if not df.empty else 0
    total_staff = len(staff_df)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Today's Shoots", today_count)
    m2.metric("Tomorrow's Bookings", tomorrow_count)
    m3.metric("Upcoming Pipelines", upcoming_count)
    m4.metric("Registered Staff Core", total_staff)
    
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Gross Projected Revenue", f"${total_rev:,.2f}")
    m6.metric("Total Outstanding Balances", f"${pending_amt:,.2f}")
    m7.metric("Completed Profiles", completed_shoots)
    m8.metric("Cancelled Postings", cancelled_count)
    
    st.markdown("---")
    
    if not df.empty and len(df_active) > 0:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Revenue Contribution by Event Type")
            rev_fig = px.pie(df_active, values="Amount", names="Event Type", hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(rev_fig, use_container_width=True)
            
        with c2:
            st.subheader("Monthly Trajectory Velocity")
            df['Month'] = pd.to_datetime(df['Booking Date']).dt.strftime('%Y-%m')
            month_df = df.groupby('Month').size().reset_index(name='Total Bookings')
            bar_fig = px.bar(month_df, x='Month', y='Total Bookings', color='Total Bookings', color_continuous_scale='Viridis')
            st.plotly_chart(bar_fig, use_container_width=True)

elif page == "➕ New Booking Entry":
    st.title("➕ Create New Booking Ledger")
    bookings_df = load_bookings()
    staff_df = load_staff()
    
    next_id = f"LF-{1001 + len(bookings_df)}"
    
    with st.form("booking_orchestration_form", clear_on_submit=True):
        st.subheader("1. Client Contact & Logistics Information")
        f1, f2 = st.columns(2)
        client_name = f1.text_input("Client Full Name *")
        client_phone = f2.text_input("Client Contact Phone Line *")
        client_email = f1.text_input("Client Notification Email Address *")
        client_address = f2.text_area("Client Billing/Home Address *", height=68)
        
        st.markdown("---")
        st.subheader("2. Assignment Details & Chronology")
        f3, f4, f5 = st.columns(3)
        event_type = f3.selectbox("Event Operational Profile Classification", EVENT_TYPES)
        event_date = f4.date_input("Target Execution Date", min_value=date.today())
        shoot_time = f5.text_input("Target Call Time / Duration", "10:00 AM")
        
        f6, f7 = st.columns(2)
        venue = f6.text_input("Venue Name *")
        maps_link = f7.text_input("Google Maps Navigation Link URL")
        
        st.markdown("---")
        st.subheader("3. Human Resource Assignment Matrix")
        staff_mode = st.radio("Staff Selection Mode", ["Assign Existing Staff Member", "Onboard & Assign a New Profile"])
        
        if staff_mode == "Assign Existing Staff Member":
            if not staff_df.empty:
                assigned_staff_name = st.selectbox("Select Staff Profile", staff_df["Staff Name"].tolist())
                new_staff_phone, new_staff_email, new_staff_role = "", "", ""
            else:
                st.info("No registered staff profiles identified.")
                assigned_staff_name = "Unassigned"
        else:
            sf1, sf2, sf3 = st.columns(3)
            new_staff_name = sf1.text_input("New Professional Name")
            new_staff_phone = sf2.text_input("New Professional Phone Line")
            new_staff_email = sf3.text_input("New Professional Email Address")
            new_staff_role = st.selectbox("Primary Functional Role Matrix Assignment", STAFF_ROLES)
            assigned_staff_name = new_staff_name
            
        st.markdown("---")
        st.subheader("4. Financial Structure Mapping")
        f8, f9, f10 = st.columns(3)
        amount = f8.number_input("Total Contract Quoted Value ($)", min_value=0.0, step=50.0)
        advance = f9.number_input("Collected Advance Deposit Amount ($)", min_value=0.0, step=50.0)
        payment_status = f10.selectbox("Payment Lifecycle Allocation Stage", ["Pending", "Partial", "Paid"])
        
        notes = st.text_area("Detailed Directives / Notes")
        submit_btn = st.form_submit_button("Lock & Finalize Structural Booking Transaction")
        
        if submit_btn:
            if not client_name or not client_phone or not client_email or not venue:
                st.error("Submission blocked: Mandatory fields missing.")
            elif not validate_email(client_email):
                st.error("Syntax Error: Client email verification failed.")
            elif not validate_phone(client_phone):
                st.error("Syntax Error: Client phone failed verification framework.")
            else:
                if not bookings_df.empty:
                    duplicate_match = bookings_df[
                        (pd.to_datetime(bookings_df["Booking Date"]).dt.date == event_date) & 
                        (bookings_df["Venue"].str.lower() == venue.lower().strip()) &
                        (bookings_df["Status"] != "Cancelled")
                    ]
                    if not duplicate_match.empty:
                        st.warning("Double Booking Warning Detected.")
                
                if staff_mode == "Onboard & Assign a New Profile" and new_staff_name.strip():
                    if validate_email(new_staff_email) and validate_phone(new_staff_phone):
                        new_staff_row = {
                            "Staff Name": new_staff_name.strip(),
                            "Staff Phone": new_staff_phone.strip(),
                            "Staff Email": new_staff_email.strip(),
                            "Role": new_staff_role
                        }
                        staff_df = pd.concat([staff_df, pd.DataFrame([new_staff_row])], ignore_index=True)
                        save_staff(staff_df)
                    else:
                        st.error("Staff metrics verification failed.")
                        st.stop()
                        
                remaining_calc = amount - advance
                new_booking = {
                    "Booking ID": next_id,
                    "Booking Date": event_date,
                    "Client Name": client_name.strip(),
                    "Phone": client_phone.strip(),
                    "Email": client_email.strip(),
                    "Address": client_address.strip(),
                    "Event Type": event_type,
                    "Venue": venue.strip(),
                    "Time": shoot_time.strip(),
                    "Assigned Staff": assigned_staff_name if assigned_staff_name else "Unassigned",
                    "Amount": amount,
                    "Advance": advance,
                    "Remaining": remaining_calc,
                    "Payment Status": payment_status,
                    "Status": "Active",
                    "Notes": f"{notes} | Maps: {maps_link}",
                    "Created Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                updated_bookings = pd.concat([bookings_df, pd.DataFrame([new_booking])], ignore_index=True)
                save_bookings(updated_bookings)
                st.success(f"System Record Written Successfully! Key Reference: {next_id}")
                dispatch_booking_emails(new_booking)

elif page == "🔍 Browse & Manage Bookings":
    st.title("🔍 Search, Filter & Mutation Administration Registry")
    df = load_bookings()
    
    if df.empty:
        st.info("The operational databases currently hold zero documented booking files.")
    else:
        st.subheader("Global Matrix Query Filter")
        sc1, sc2, _ = st.columns([2, 2, 3])
        search_query = sc1.text_input("Fuzzy Search by Client Name, ID, Phone, or Venue Location")
        filter_status = sc2.selectbox("Temporal Scope Constraint Engine", [
            "All Bookings", "Today's Booking", "Tomorrow", "This Week", "Completed Only", "Pending Payment Ledger", "Upcoming Pipeline"
        ])
        
        if search_query:
            q = search_query.lower()
            df = df[
                df["Client Name"].str.lower().str.contains(q) |
                df["Booking ID"].str.lower().str.contains(q) |
                df["Phone"].astype(str).str.contains(q) |
                df["Venue"].str.lower().str.contains(q)
            ]
            
        today = date.today()
        if filter_status == "Today's Booking":
            df = df[pd.to_datetime(df["Booking Date"]).dt.date == today]
        elif filter_status == "Tomorrow":
            df = df[pd.to_datetime(df["Booking Date"]).dt.date == (today + timedelta(days=1))]
        elif filter_status == "This Week":
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            df = df[(pd.to_datetime(df["Booking Date"]).dt.date >= start_week) & (pd.to_datetime(df["Booking Date"]).dt.date <= end_week)]
        elif filter_status == "Completed Only":
            df = df[df["Status"] == "Completed"]
        elif filter_status == "Pending Payment Ledger":
            df = df[df["Payment Status"].isin(["Pending", "Partial"])]
        elif filter_status == "Upcoming Pipeline":
            df = df[pd.to_datetime(df["Booking Date"]).dt.date > today]
            
        st.dataframe(df, use_container_width=True)
        
        d1, d2, _ = st.columns([1, 1, 5])
        with open(BOOKINGS_XLSX, "rb") as f:
            d1.download_button("📥 Export Master Matrix (.XLSX)", f, file_name=BOOKINGS_XLSX, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with open(BOOKINGS_CSV, "rb") as f:
            d2.download_button("📥 Export Compiled Record (.CSV)", f, file_name=BOOKINGS_CSV, mime="text/csv")
            
        st.markdown("---")
        st.subheader("Modify Matrix Row Record Elements")
        selected_id = st.selectbox("Target Record Selection Matrix ID via Tracking Key", ["Select Index Pointer..."] + df["Booking ID"].tolist())
        
        if selected_id != "Select Index Pointer...":
            master_df = load_bookings()
            target_row_idx = master_df[master_df["Booking ID"] == selected_id].index[0]
            target_data = master_df.loc[target_row_idx]
            
            with st.expander("Active Row State Mutation Editor Portal", expanded=True):
                ec1, ec2, ec3 = st.columns(3)
                edit_name = ec1.text_input("Client Name Entry Mod", value=target_data["Client Name"])
                edit_phone = ec2.text_input("Client Phone Entry Mod", value=target_data["Phone"])
                edit_email = ec3.text_input("Client Email Entry Mod", value=target_data["Email"])
                
                ec4, ec5, ec6 = st.columns(3)
                edit_venue = ec4.text_input("Venue Assignment Modifier", value=target_data["Venue"])
                edit_amount = ec5.number_input("Quoted Asset Modification Contract Value", value=float(target_data["Amount"]))
                edit_advance = ec6.number_input("Advance Asset Matrix Adjustment Value", value=float(target_data["Advance"]))
                
                ec7, ec8, ec9 = st.columns(3)
                edit_pay_status = ec7.selectbox("Update Payment Status Tier", ["Pending", "Partial", "Paid"], index=["Pending", "Partial", "Paid"].index(target_data["Payment Status"]))
                edit_job_status = ec8.selectbox("Update Event Allocation Stage Lifecycle", ["Active", "Completed", "Cancelled"], index=["Active", "Completed", "Cancelled"].index(target_data["Status"]))
                staff_df = load_staff()
                edit_staff = ec9.selectbox("Reassign Field Personnel Profile Matrix", staff_df["Staff Name"].tolist() if not staff_df.empty else ["Unassigned"])
                
                edit_notes = st.text_area("Adjust Internal Transaction Log References", value=target_data["Notes"])
                mc1, mc2, _ = st.columns([1, 1, 4])
                
                if mc1.button("Save Applied Structural Modifications"):
                    master_df.at[target_row_idx, "Client Name"] = edit_name
                    master_df.at[target_row_idx, "Phone"] = edit_phone
                    master_df.at[target_row_idx, "Email"] = edit_email
                    master_df.at[target_row_idx, "Venue"] = edit_venue
                    master_df.at[target_row_idx, "Amount"] = edit_amount
                    master_df.at[target_row_idx, "Advance"] = edit_advance
                    master_df.at[target_row_idx, "Remaining"] = edit_amount - edit_advance
                    master_df.at[target_row_idx, "Payment Status"] = edit_pay_status
                    master_df.at[target_row_idx, "Status"] = edit_job_status
                    master_df.at[target_row_idx, "Assigned Staff"] = edit_staff
                    master_df.at[target_row_idx, "Notes"] = edit_notes
                    
                    save_bookings(master_df)
                    st.success("Target database transformation matrix write phase finalized completely.")
                    st.rerun()
                    
                if mc2.button("⚠️ Erase Record Index Completely"):
                    master_df = master_df.drop(target_row_idx)
                    save_bookings(master_df)
                    st.warning("Target document context vector eradicated from data stream indices successfully.")
                    st.rerun()

elif page == "📅 Studio Work Calendar":
    st.title("📅 Production Chronology Calendar Map")
    df = load_bookings()
    today_str = date.today().strftime("%Y-%m-%d")
    
    st.subheader(f"Schedule Reference Metrics Grid — System Clock Base Point: {today_str}")
    
    if df.empty:
        st.info("No recorded actions queued inside data stores.")
    else:
        calendar_df = df.copy()
        calendar_df["Booking Date Formatted"] = pd.to_datetime(calendar_df["Booking Date"]).dt.strftime("%Y-%m-%d")
        calendar_df = calendar_df.sort_values(by="Booking Date", ascending=True)
        
        for unique_date, group in calendar_df.groupby("Booking Date Formatted"):
            is_today = (unique_date == today_str)
            box_header = f"🗓️ {unique_date} (TODAY'S PRODUCTION WAVE)" if is_today else f"📅 {unique_date}"
            
            with st.container():
                if is_today:
                    st.markdown(f"<div style='border-left: 5px solid #FF4B4B; padding-left:10px; background-color:rgba(255,75,75,0.05); margin-bottom:10px;'>", unsafe_allow_html=True)
                st.markdown(f"#### {box_header}")
                for _, row in group.iterrows():
                    status_badge = "🟢 Active" if row["Status"] == "Active" else "🔵 Completed" if row["Status"] == "Completed" else "🔴 Cancelled"
                    st.markdown(f"* **{row['Time']}** | {row['Event Type']} - _Client:_ {row['Client Name']} | _Venue:_ `{row['Venue']}` | _Personnel:_ **{row['Assigned Staff']}** | {status_badge}")
                if is_today:
                    st.markdown("</div>", unsafe_allow_html=True)
                st.markdown("---")

elif page == "⚙️ Settings & Configuration":
    st.title("⚙️ System Variable Setup & Infrastructure Configurations")
    current_settings = load_settings()
    
    with st.form("infrastructure_settings_form"):
        st.subheader("Brand Customization Metrics")
        sc1, sc2 = st.columns(2)
        biz_name = sc1.text_input("Operational Entity/Studio Trading Name", value=current_settings.get("business_name", ""))
        owner_n = sc2.text_input("Account Owner Name Identifier", value=current_settings.get("owner_name", ""))
        owner_em = sc1.text_input("Administrative Notification Target Email Address", value=current_settings.get("owner_email", ""))
        biz_ph = sc2.text_input("Studio Support Line Number Address", value=current_settings.get("business_phone", ""))
        biz_addr = st.text_input("Physical Core Studio Address Locations", value=current_settings.get("business_address", ""))
        
        st.markdown("---")
        st.subheader("SMTP Secure Gateway Mail Delivery Routing Setup")
        sm1, sm2, sm3 = st.columns([2, 2, 1])
        smtp_e = sm1.text_input("SMTP Authorized Mail Server Account User Login ID", value=current_settings.get("smtp_email", ""))
        smtp_p = sm2.text_input("SMTP Account Key/Secret Token Password", value=current_settings.get("smtp_password", ""), type="password")
        smtp_s = sm1.text_input("Host Address Server Destination Domain Pointer Target", value=current_settings.get("smtp_server", "smtp.gmail.com"))
        smtp_port = sm3.number_input("Target Network Port Number", value=int(current_settings.get("smtp_port", 587)))
        
        save_settings_btn = st.form_submit_button("Commit Changes into Local Infrastructure Storage Vector")
        
        if save_settings_btn:
            updated_settings_payload = {
                "business_name": biz_name.strip(),
                "owner_name": owner_n.strip(),
                "owner_email": owner_em.strip(),
                "smtp_email": smtp_e.strip(),
                "smtp_password": smtp_p,
                "smtp_server": smtp_s.strip(),
                "smtp_port": int(smtp_port),
                "business_phone": biz_ph.strip(),
                "business_address": biz_addr.strip()
            }
            save_settings(updated_settings_payload)
            st.success("Configuration modifications saved successfully.")
