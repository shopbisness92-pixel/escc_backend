import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor
import joblib

# Load dataset
data = pd.read_csv("dataset/dataset.csv")

# Encode categorical columns
encoder = LabelEncoder()
for col in ["compliance_framework", "scan_type"]:
    data[col] = encoder.fit_transform(data[col])

# Features & Target
X = data.drop(["project_name", "description", "score"], axis=1)
y = data["score"]

# Train/Test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Model
model = RandomForestRegressor(
    n_estimators=200,
    random_state=42
)

model.fit(X_train, y_train)

# Save model
joblib.dump(model, "model.pkl")

print("✅ ESCC AI Model Trained Successfully")
