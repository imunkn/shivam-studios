import streamlit as st
import pandas as pd
import json
import os
import re
import smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import plotly.express as px
from apscheduler.schedulers.background import BackgroundScheduler

# Set Streamlit Page Configuration - optimized for responsive screens
st.set_page_config(
    page_title="LensFlow Mobile",
    page_icon="📸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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

def init_storage():
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
        if not df.empty:
            df["Booking Date"] = pd.to_datetime(df["Booking Date"]).dt.date
            df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce').fillna(0.0)
            df["Advance"] = pd.to_numeric(df["Advance"], errors='coerce').fillna(0.0)
            df["Remaining"] = pd.to_numeric(df["Remaining"], errors='coerce').fillna(0.0)
        return df
    except Exception:
        try:
            return pd.read_csv(BOOKINGS_CSV, dtype={"Booking ID": str, "Phone": str})
        except Exception:
            booking_cols = [
                "Booking ID", "Booking Date", "Client Name", "Phone", "Email", 
                "Address", "Event Type", "Venue", "Time", "Assigned Staff", 
                "Amount", "Advance", "Remaining", "Payment Status", "Status", "Notes", "Created Time"
            ]
            return pd.DataFrame(columns=booking_cols)

def save_bookings(df):
    df.to_excel(BOOKINGS_XLSX, index=False)
    df.to_csv(BOOKINGS_CSV, index=False)

def load_staff():
    try:
        return pd.read_excel(STAFF_XLSX, dtype={"Staff Phone": str})
    except Exception:
        return pd.DataFrame(columns=["Staff Name", "Staff Phone", "Staff Email", "Role"])

def save_staff(df):
    df.to_excel(STAFF_XLSX, index=False)

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def validate_phone(phone):
    return re.match(r"^\+?1?\d{9,15}$", phone) is not None

def send_html_email(to_email, subject, html_body):
    settings = load_settings()
    if not settings.get("smtp_email") or not settings.get("smtp_password"):
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

def dispatch_booking_emails(booking_data):
    settings = load_settings()
    client_html = f"<html><body><h2>Booking Confirmed! 🎉</h2><p>ID: {booking_data['Booking ID']}<br>Date: {booking_data['Booking Date']}</p></body></html>"
    send_html_email(booking_data['Email'], f"Booking Confirmed - ID: {booking_data['Booking ID']}", client_html)

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
    df = load_bookings()
    staff_df = load_staff()
    today = date.today()
    
    if not df.empty:
        df_active = df[df["Status"] != "Cancelled"]
        total_rev = df_active["Amount"].sum()
        pending_amt = df_active["Remaining"].sum()
        
        st.metric("Gross Revenue", f"${total_rev:,.2f}")
        st.metric("Outstanding Balance", f"${pending_amt:,.2f}")
        st.metric("Active Bookings", len(df_active))
        
        fig = px.pie(df_active, values="Amount", names="Event Type", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No bookings recorded yet.")

elif page == "➕ New Booking":
    st.subheader("Add Booking Ledger")
    bookings_df = load_bookings()
    staff_df = load_staff()
    
    next_id = f"LF-{1001 + len(bookings_df)}"
    
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
        
        staff_list = staff_df["Staff Name"].tolist() if not staff_df.empty else []
        staff_list.append("None / Unassigned")
        assigned_staff = st.selectbox("Assign Staff", staff_list)
        
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
                    "Booking ID": next_id, "Booking Date": event_date, "Client Name": client_name.strip(),
                    "Phone": client_phone.strip(), "Email": client_email.strip(), "Address": client_address.strip(),
                    "Event Type": event_type, "Venue": venue.strip(), "Time": shoot_time.strip(),
                    "Assigned Staff": assigned_staff, "Amount": amount, "Advance": advance,
                    "Remaining": amount - advance, "Payment Status": payment_status, "Status": "Active",
                    "Notes": f"{notes} | Maps: {maps_link}", "Created Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                updated_bookings = pd.concat([bookings_df, pd.DataFrame([new_booking])], ignore_index=True)
                save_bookings(updated_bookings)
                st.success(f"Booking Saved! ID: {next_id}")
                dispatch_booking_emails(new_booking)

elif page == "🔍 Search & Edit":
    df = load_bookings()
    if df.empty:
        st.info("No data available.")
    else:
        search = st.text_input("Search by Name or ID")
        if search:
            df = df[df["Client Name"].str.lower().str.contains(search.lower()) | df["Booking ID"].str.lower().str.contains(search.lower())]
        
        st.dataframe(df[["Booking ID", "Client Name", "Booking Date", "Status"]], use_container_width=True)
        
        selected_id = st.selectbox("Select ID to Edit/Delete", ["Choose..."] + df["Booking ID"].tolist())
        if selected_id != "Choose...":
            row_idx = df[df["Booking ID"] == selected_id].index[0]
            target = df.loc[row_idx]
            
            edit_status = st.selectbox("Job Status", ["Active", "Completed", "Cancelled"], index=["Active", "Completed", "Cancelled"].index(target["Status"]))
            edit_pay = st.selectbox("Payment Stage", ["Pending", "Partial", "Paid"], index=["Pending", "Partial", "Paid"].index(target["Payment Status"]))
            
            if st.button("Update Record"):
                master_df = load_bookings()
                master_df.at[row_idx, "Status"] = edit_status
                master_df.at[row_idx, "Payment Status"] = edit_pay
                save_bookings(master_df)
                st.success("Record updated!")
                st.rerun()
                
            if st.button("Delete Permanently"):
                master_df = load_bookings()
                master_df = master_df.drop(row_idx)
                save_bookings(master_df)
                st.warning("Record deleted.")
                st.rerun()

elif page == "📅 Work List":
    df = load_bookings()
    if df.empty:
        st.info("No scheduled records.")
    else:
        df["Booking Date Formatted"] = pd.to_datetime(df["Booking Date"]).dt.strftime("%Y-%m-%d")
        df = df.sort_values(by="Booking Date")
        for unique_date, group in df.groupby("Booking Date Formatted"):
            st.markdown(f"#### 📅 {unique_date}")
            for _, row in group.iterrows():
                st.markdown(f"**{row['Time']}** - {row['Event Type']} for *{row['Client Name']}* at `{row['Venue']}` ({row['Status']})")
            st.markdown("---")

elif page == "⚙️ Settings":
    current_settings = load_settings()
    with st.form("settings_form"):
        biz_name = st.text_input("Studio Name", value=current_settings.get("business_name", ""))
        owner_em = st.text_input("Owner Email", value=current_settings.get("owner_email", ""))
        smtp_e = st.text_input("SMTP Email", value=current_settings.get("smtp_email", ""))
        smtp_p = st.text_input("SMTP Password", value=current_settings.get("smtp_password", ""), type="password")
        
        if st.form_submit_button("Save Configurations"):
            current_settings.update({"business_name": biz_name, "owner_email": owner_em, "smtp_email": smtp_e, "smtp_password": smtp_p})
            save_settings(current_settings)
            st.success("Settings saved locally.")
            
