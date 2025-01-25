import requests
import pandas as pd
import time
import streamlit as st
from collections import deque

API_KEY = '1fe1ac47121e0b87282c244c8f59c08b'

def get_weather_data(api_key, lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Error fetching weather data")
        return None

def parse_weather_data(weather_data):
    for forecast in weather_data['list']:
        dt = forecast['dt_txt']
        temp = forecast['main']['temp']
        humidity = forecast['main']['humidity']
        rain = forecast.get('rain', {}).get('3h', 0)
        pop = forecast.get('pop', 0)
        wind_speed = forecast['wind']['speed']
        yield {
            'datetime': dt,
            'temperature': temp,
            'humidity': humidity,
            'rain_3h': rain,
            'precipitation_probability': pop,
            'wind_speed': wind_speed
        }

def collect_moisture_data(csv_file, row_index):
    df = pd.read_csv(csv_file, header=None)
    moisture_data = {f"Field_{i+1}": df.iloc[row_index, i] for i in range(df.shape[1])}
    return moisture_data

def is_safe_state(available, allocation, need):
    work = available[:]
    finish = [False] * len(need)

    safe_sequence = []
    while len(safe_sequence) < len(need):
        found = False
        for i in range(len(need)):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(len(work))):
                for j in range(len(work)):
                    work[j] += allocation[i][j]
                finish[i] = True
                safe_sequence.append(i)
                found = True
        if not found:
            return False, safe_sequence  # Not in a safe state
    
    return True, safe_sequence

def banker_algorithm(total_water, allocation, need):
    available = [total_water - sum(row) for row in zip(*allocation)]
    is_safe, safe_sequence = is_safe_state(available, allocation, need)
    
    return is_safe, safe_sequence

def efficient_water_allocation(moisture_data, current_weather, crop_water_requirement, allocation, need, field_index):
    rain = current_weather['rain_3h']
    temp = current_weather['temperature']
    humidity = current_weather['humidity']
    
    rain_factor = 1 - min(rain / 10, 1)
    temp_factor = 1 + (temp - 25) / 25
    humidity_factor = 1 - (humidity / 100)
    
    field = f'Field_{field_index+1}'
    moisture = moisture_data[field]
    irrigation_need = crop_water_requirement[field] * (1 - moisture)
    irrigation_need *= rain_factor
    irrigation_need *= temp_factor
    irrigation_need *= humidity_factor
    
    is_safe, _ = banker_algorithm(total_water, allocation, need)
    
    if is_safe:
        allocation[field_index][0] = irrigation_need
        need[field_index][0] -= irrigation_need
        return irrigation_need
    else:
        return 0

def irrigation_system_banker(api_key, lat, lon, fields, csv_file):
    df = pd.read_csv(csv_file, header=None)
    
    row_index = 0
    field_queue = deque([f'Field_{i+1}' for i in range(fields)])
    
    allocation = [[0] for _ in range(fields)]
    need = [[crop_water_requirement[f'Field_{i+1}']] for i in range(fields)]
    
    irrigation_data = []
    
    while row_index < len(df):
        weather_data = get_weather_data(api_key, lat, lon)
        if weather_data is None:
            break
        parsed_weather = parse_weather_data(weather_data)
        current_weather = next(parsed_weather)
        
        moisture_data = collect_moisture_data(csv_file, row_index)
        
        current_field = field_queue.popleft()
        field_index = int(current_field.split('_')[1]) - 1
        field_queue.append(current_field)
        
        water_allocated = efficient_water_allocation(
            moisture_data, current_weather, crop_water_requirement, 
            allocation, need, field_index
        )
        
        irrigation_data.append({
            'field': current_field,
            'water_allocated': water_allocated,
            'weather': current_weather
        })
        
        row_index += 1

    return irrigation_data

fields = 5
crop_water_requirement = {
    'Field_1': 1.0, 
    'Field_2': 1.2,
    'Field_3': 0.9,
    'Field_4': 1.1,
    'Field_5': 0.8
}

total_water = 100  

st.title("Irrigation System Management")
st.sidebar.header("Settings")

lat = st.sidebar.text_input("Latitude", value='16.5167')
lon = st.sidebar.text_input("Longitude", value='80.6167')
csv_file = st.sidebar.file_uploader("Upload Moisture Data CSV", type=["csv"])
if csv_file:
    df = pd.read_csv(csv_file)
    st.sidebar.write("Uploaded Moisture Data:")
    st.sidebar.dataframe(df)

if st.sidebar.button("Start Irrigation System"):
    if csv_file:
        with st.spinner("Fetching and processing data..."):
            irrigation_data = irrigation_system_banker(API_KEY, lat, lon, fields, csv_file.name)
        st.success("Irrigation System Completed!")
        
        # Display irrigation data
        st.subheader("Irrigation Allocation Data")
        allocation_df = pd.DataFrame(irrigation_data)
        st.dataframe(allocation_df)

        # Plotting
        st.subheader("Water Allocated per Field")
        st.bar_chart(allocation_df.set_index('field')['water_allocated'])

        # Weather Data Display
        st.subheader("Latest Weather Data")
        latest_weather = irrigation_data[-1]['weather']
        st.write(f"Temperature: {latest_weather['temperature']} °C")
        st.write(f"Humidity: {latest_weather['humidity']} %")
        st.write(f"Rain (3h): {latest_weather['rain_3h']} mm")
    else:
        st.error("Please upload a moisture data CSV file before starting.")