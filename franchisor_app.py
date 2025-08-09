import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials

# Page config
st.set_page_config(
    page_title="MyFitPod Franchisor Command Center",
    page_icon="🏢",
    layout="wide"
)

# Authentication setup
@st.cache_resource
def init_gspread():
    """Initialize Google Sheets connection using service account"""
    try:
        # You'll need to upload your JSON credentials file to Streamlit
        # For now, we'll use Streamlit secrets (safer approach)
        credentials_dict = {
            "type": st.secrets["gcp_service_account"]["type"],
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"],
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
            "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        }
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

# Location and date configurations
LOCATIONS = {
    "Oxford East": {
        "sheet_name": "Oxford East Monthly Tracker",
        "years": [2025],
        "months": {
            2025: ["May 25", "Jun 25", "Jul 25", "Aug 25", "Sep 25", "Oct 25", "Nov 25", "Dec 25"]
        }
    },
    "Milton Keynes": {
        "sheet_name": "Milton Keynes Monthly Tracker", 
        "years": [2025],
        "months": {
            2025: ["May 25", "Jun 25", "Jul 25", "Aug 25", "Sep 25", "Oct 25", "Nov 25", "Dec 25"]
        }
    },
    "Berkhamsted": {
        "sheet_name": "Berkhamsted Monthly Revenue Tracker",
        "years": [2025], 
        "months": {
            2025: ["May 25", "Jun 25", "Jul 25", "Aug 25", "Sep 25", "Oct 25", "Nov 25", "Dec 25"]
        }
    },
    "Basingstoke": {
        "sheet_name": "Basingstoke Monthly Tracker",
        "years": [2025],
        "months": {
            2025: ["May 25", "Jun 25", "Jul 25", "Aug 25", "Sep 25", "Oct 25", "Nov 25", "Dec 25"]
        }
    },
    "Aylesbury": {
        "sheet_name": "Aylesbury Monthly Tracker",
        "years": [2023, 2024, 2025],
        "months": {
            2023: ["Feb 23", "Mar 23", "Apr 23", "May 23", "Jun 23", "Jul 23", "Aug 23", "Sep 23", "Oct 23", "Nov 23", "Dec 23"],
            2024: ["Jan 24", "Feb 24", "Mar 24", "Apr 24", "May 24", "Jun 24", "Jul 24", "Aug 24", "Sep 24", "Oct 24", "Nov 24", "Dec 24"],
            2025: ["Jan 25", "Feb 25", "Mar 25", "Apr 25", "May 25", "Jun 25", "Jul 25", "Aug 25", "Sep 25", "Oct 25", "Nov 25", "Dec 25"]
        }
    }
}

def load_sheet_data(gc, location, year, month):
    """Load data from specific Google Sheet tab"""
    try:
        sheet_name = LOCATIONS[location]["sheet_name"]
        sheet = gc.open(sheet_name)
        
        # Get the specific month tab
        worksheet = sheet.worksheet(month)
        
        # Get all data - handle empty columns properly
        try:
            data = worksheet.get_all_records()
        except Exception as e:
            if "duplicates" in str(e):
                # Handle duplicate empty headers by getting raw data
                all_values = worksheet.get_all_values()
                if len(all_values) > 1:
                    headers = all_values[0]
                    # Take only first 4 columns to avoid empty columns
                    clean_headers = headers[:4] if len(headers) >= 4 else headers
                    rows = all_values[1:]
                    
                    data = []
                    for row in rows:
                        if len(row) >= len(clean_headers):
                            row_dict = {}
                            for i, header in enumerate(clean_headers):
                                row_dict[header] = row[i] if i < len(row) else ''
                            data.append(row_dict)
                else:
                    data = []
            else:
                raise e
        
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        # Clean and standardize column names - use only first 4 columns
        if len(df.columns) >= 4:
            # Take only the first 4 columns and rename them
            df = df.iloc[:, :4].copy()
            df.columns = ['DateTime', 'Product', 'Quantity', 'Amount']
            
            # Convert Amount to numeric
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
            
            # Parse datetime
            df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
            df = df.dropna(subset=['DateTime'])
            
            # Add metadata
            df['Location'] = location
            df['Year'] = year
            df['Month'] = month
            
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error loading data for {location} {month}: {str(e)}")
        return pd.DataFrame()

def calculate_revenue_metrics(df):
    """Calculate key revenue metrics"""
    if df.empty:
        return {
            'total_revenue': 0,
            'transaction_count': 0,
            'avg_transaction': 0,
            'unique_products': 0,
            'top_product': 'N/A',
            'daily_average': 0
        }
    
    total_revenue = df['Amount'].sum()
    transaction_count = len(df)
    avg_transaction = total_revenue / transaction_count if transaction_count > 0 else 0
    unique_products = df['Product'].nunique()
    
    # Top product by revenue
    product_revenue = df.groupby('Product')['Amount'].sum()
    top_product = product_revenue.idxmax() if not product_revenue.empty else 'N/A'
    
    # Daily average (assuming month has 30 days for simplicity)
    daily_average = total_revenue / 30
    
    return {
        'total_revenue': total_revenue,
        'transaction_count': transaction_count,
        'avg_transaction': avg_transaction,
        'unique_products': unique_products,
        'top_product': top_product,
        'daily_average': daily_average
    }

def create_revenue_chart(df):
    """Create daily revenue chart"""
    if df.empty:
        return go.Figure()
    
    # Group by date
    daily_revenue = df.groupby(df['DateTime'].dt.date)['Amount'].sum().reset_index()
    daily_revenue.columns = ['Date', 'Revenue']
    
    fig = px.line(
        daily_revenue, 
        x='Date', 
        y='Revenue',
        title='Daily Revenue Trend',
        markers=True
    )
    
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Revenue (£)",
        showlegend=False,
        height=400
    )
    
    return fig

def create_product_analysis(df):
    """Create product performance analysis"""
    if df.empty:
        return go.Figure(), pd.DataFrame()
    
    # Product performance
    product_stats = df.groupby('Product').agg({
        'Amount': ['sum', 'count', 'mean']
    }).round(2)
    
    product_stats.columns = ['Total Revenue', 'Transaction Count', 'Avg Value']
    product_stats = product_stats.sort_values('Total Revenue', ascending=False)
    
    # Create chart
    fig = px.bar(
        product_stats.reset_index(),
        x='Product',
        y='Total Revenue',
        title='Product Performance by Revenue'
    )
    
    fig.update_layout(
        xaxis_title="Product",
        yaxis_title="Revenue (£)",
        xaxis_tickangle=-45,
        height=400
    )
    
    return fig, product_stats

def main():
    st.title("🏢 MyFitPod Franchisor Command Center")
    st.markdown("**Enterprise Franchise Analytics & Performance Monitoring**")
    
    # Initialize Google Sheets connection
    gc = init_gspread()
    if not gc:
        st.error("❌ Could not connect to Google Sheets. Please check your credentials.")
        st.stop()
    
    # Sidebar filters
    st.sidebar.header("📊 Analytics Filters")
    
    # Location selector
    location = st.sidebar.selectbox(
        "📍 Select Location:",
        options=list(LOCATIONS.keys()),
        index=0
    )
    
    # Year selector (dynamic based on location)
    available_years = LOCATIONS[location]["years"]
    year = st.sidebar.selectbox(
        "📅 Select Year:",
        options=available_years,
        index=len(available_years)-1  # Default to most recent year
    )
    
    # Month selector (dynamic based on location and year)
    available_months = LOCATIONS[location]["months"][year]
    month = st.sidebar.selectbox(
        "📊 Select Month:",
        options=available_months,
        index=len(available_months)-1  # Default to most recent month
    )
    
    # Load data
    with st.spinner(f"Loading data for {location} - {month}..."):
        df = load_sheet_data(gc, location, year, month)
    
    if df.empty:
        st.warning(f"⚠️ No data available for {location} - {month}")
        st.info("This could mean:")
        st.info("• The month tab doesn't exist yet")
        st.info("• The sheet is empty")
        st.info("• There's a connection issue")
        return
    
    # Calculate metrics
    metrics = calculate_revenue_metrics(df)
    
    # Executive Summary
    st.header(f"📈 {location} Performance - {month}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 Total Revenue",
            f"£{metrics['total_revenue']:,.2f}",
            help="Total revenue for the selected period"
        )
    
    with col2:
        st.metric(
            "📊 Transactions", 
            f"{metrics['transaction_count']:,}",
            help="Number of transactions completed"
        )
    
    with col3:
        st.metric(
            "💳 Avg Transaction",
            f"£{metrics['avg_transaction']:.2f}",
            help="Average transaction value"
        )
    
    with col4:
        st.metric(
            "📅 Daily Average",
            f"£{metrics['daily_average']:.2f}",
            help="Average revenue per day"
        )
    
    # Performance Analysis
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Daily Revenue Trend")
        revenue_chart = create_revenue_chart(df)
        st.plotly_chart(revenue_chart, use_container_width=True)
        
        # Key insights
        st.subheader("💡 Key Insights")
        st.write(f"🏆 **Top Product:** {metrics['top_product']}")
        st.write(f"🛍️ **Product Variety:** {metrics['unique_products']} different products sold")
        
        # Performance indicators
        if metrics['total_revenue'] > 6000:
            st.success("✅ Excellent performance - above £6K target!")
        elif metrics['total_revenue'] > 4000:
            st.warning("⚠️ Good performance - approaching target")
        else:
            st.error("🔴 Below target - needs attention")
    
    with col2:
        st.subheader("🛍️ Product Performance")
        product_chart, product_stats = create_product_analysis(df)
        st.plotly_chart(product_chart, use_container_width=True)
        
        # Product performance table
        st.subheader("📊 Product Breakdown")
        st.dataframe(product_stats, use_container_width=True)
    
    # Raw data section (expandable)
    with st.expander("📋 View Raw Transaction Data"):
        st.dataframe(
            df[['DateTime', 'Product', 'Amount']].sort_values('DateTime', ascending=False),
            use_container_width=True
        )
        
        # Download option
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name=f"{location}_{month}_data.csv",
            mime="text/csv"
        )
    
    # Footer
    st.markdown("---")
    st.markdown("🔄 Data updates automatically when you modify your Google Sheets")
    st.markdown(f"📊 Currently viewing: **{location}** | **{month}** | **{len(df)} transactions**")

if __name__ == "__main__":
    main()
