"""
AI Prediction Models for SmartBookingAI - FINAL PRODUCTION VERSION
Implements Random Forest for booking demand prediction
"""

import numpy as np
import pandas as pd
import sqlite3
import os
import joblib
from datetime import datetime
from contextlib import contextmanager
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        db_path = os.path.join(parent_dir, "booking_services", "booking.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

class BookingDemandPredictor:
    """
    ML model for predicting booking demand using Random Forest
    Trained on synthetic historical booking data
    """
    
    def __init__(self, model_type="random_forest"):
        """Initialize predictor with consistent feature set"""
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Model save paths
        model_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(model_dir, f"{model_type}_model.pkl")
        self.scaler_path = os.path.join(model_dir, f"{model_type}_scaler.pkl")
        self.metadata_path = os.path.join(model_dir, f"{model_type}_metadata.pkl")
        
        # CRITICAL: Feature names must match training exactly
        self.feature_names = [
            'day_of_week', 'is_weekend', 'month', 'hour',
            'is_morning', 'is_afternoon', 'is_evening', 'is_business_hours',
            'is_peak_hour', 'is_summer', 'is_winter',
            'event_id', 'max_capacity', 'duration_minutes', 'capacity_normalized'
        ]
        
        self.max_capacity_for_normalization = 50.0  # Default, updated during training
        
        print(f"Initialized {model_type} predictor")
        print(f"Model path: {self.model_path}")
    
    def load_training_data(self):
        """Load synthetic training data from booking_history table"""
        
        print("Loading training data from booking_history...")
        
        with get_db_connection() as conn:
            query = """
                SELECT 
                    bh.day_of_week,
                    bh.is_weekend,
                    bh.month,
                    CAST(strftime('%H', bh.booking_time) AS INTEGER) as hour,
                    CASE WHEN bh.status = 'confirmed' THEN 1 ELSE 0 END as is_booked,
                    ts.event_id,
                    ts.max_capacity,
                    e.duration_minutes
                FROM booking_history bh
                JOIN time_slots ts ON bh.time_slot_id = ts.id
                JOIN events e ON ts.event_id = e.id
            """
            
            df = pd.read_sql_query(query, conn)
            
            if len(df) == 0:
                raise ValueError(
                    "No training data found in booking_history table. "
                    "Please generate synthetic data first using /ai/generate-data endpoint"
                )
            
            print(f"✓ Loaded {len(df)} training records")
            return df
    
    def engineer_features(self, df):
        """Engineer time-based and derived features"""
        
        # Time period features
        df['is_morning'] = ((df['hour'] >= 6) & (df['hour'] < 12)).astype(int)
        df['is_afternoon'] = ((df['hour'] >= 12) & (df['hour'] < 17)).astype(int)
        df['is_evening'] = ((df['hour'] >= 17) & (df['hour'] < 22)).astype(int)
        df['is_business_hours'] = ((df['hour'] >= 9) & (df['hour'] <= 17)).astype(int)
        
        # Peak hours (10-11 AM, 2-3 PM)
        df['is_peak_hour'] = df['hour'].isin([10, 11, 14, 15]).astype(int)
        
        # Seasonal features
        df['is_summer'] = df['month'].isin([6, 7, 8]).astype(int)
        df['is_winter'] = df['month'].isin([12, 1, 2]).astype(int)
        
        # Capacity normalization
        max_cap = df['max_capacity'].max()
        if max_cap > 0:
            df['capacity_normalized'] = df['max_capacity'] / max_cap
            self.max_capacity_for_normalization = max_cap
        else:
            df['capacity_normalized'] = 0.0
            self.max_capacity_for_normalization = 50.0
        
        # Ensure is_weekend is integer
        df['is_weekend'] = df['is_weekend'].astype(int)
        
        return df
    
    def prepare_features(self, df):
        """Prepare feature matrix X and target variable y"""
        
        df = self.engineer_features(df)
        
        # Select features in exact order
        X = df[self.feature_names]
        y = df['is_booked']
        
        print(f"Training features: {self.feature_names}")
        print(f"Feature matrix shape: {X.shape}")
        print(f"Target distribution: {y.value_counts().to_dict()}")
        
        return X, y
    
    def train(self, test_size=0.2, random_state=42):
        """Train the Random Forest model"""
        
        print(f"\n{'='*60}")
        print(f"Training {self.model_type.upper()} Model")
        print(f"{'='*60}\n")
        
        # Load and prepare data
        df = self.load_training_data()
        X, y = self.prepare_features(df)
        
        # Split into train/test sets
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=test_size, 
            random_state=random_state,
            stratify=y  # Maintain class distribution
        )
        
        print(f"Training set size: {len(X_train)}")
        print(f"Testing set size: {len(X_test)}")
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Initialize Random Forest
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=random_state,
            n_jobs=-1,
            class_weight='balanced'  # Handle imbalanced classes
        )
        
        # Train model
        print("\nTraining model...")
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True
        print("✓ Training complete")
        
        # Evaluate performance
        y_pred_train = self.model.predict(X_train_scaled)
        y_pred_test = self.model.predict(X_test_scaled)
        
        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred_test)
        precision = precision_score(y_test, y_pred_test)
        recall = recall_score(y_test, y_pred_test)
        f1 = f1_score(y_test, y_pred_test)
        
        print(f"\n{'='*60}")
        print("MODEL PERFORMANCE METRICS")
        print(f"{'='*60}")
        print(f"Training Accuracy:   {train_acc:.4f}")
        print(f"Testing Accuracy:    {test_acc:.4f}")
        print(f"Precision:           {precision:.4f}")
        print(f"Recall:              {recall:.4f}")
        print(f"F1-Score:            {f1:.4f}")
        
        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            print(f"\n{'='*60}")
            print("TOP 5 MOST IMPORTANT FEATURES")
            print(f"{'='*60}")
            
            importances = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            for idx, row in importances.head(5).iterrows():
                print(f"{row['feature']:.<30} {row['importance']:.4f}")
        
        print(f"\n{'='*60}\n")
        
        return {
            'train_accuracy': float(train_acc),
            'test_accuracy': float(test_acc),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1)
        }
    
    def create_prediction_features(self, slot_info):
        """
        Create feature dictionary from time slot info
        MUST match training feature engineering exactly
        """
        
        # Parse start time
        if isinstance(slot_info['start_time'], str):
            start_time = datetime.fromisoformat(slot_info['start_time'].replace('Z', '+00:00'))
        else:
            start_time = slot_info['start_time']
        
        # Extract basic features
        day_of_week = start_time.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        month = start_time.month
        hour = start_time.hour
        
        # Event features
        event_id = int(slot_info['event_id'])
        max_capacity = int(slot_info['max_capacity'])
        duration_minutes = int(slot_info.get('duration_minutes', 60))
        
        # Engineer time features (MUST match training logic)
        is_morning = 1 if 6 <= hour < 12 else 0
        is_afternoon = 1 if 12 <= hour < 17 else 0
        is_evening = 1 if 17 <= hour < 22 else 0
        is_business_hours = 1 if 9 <= hour <= 17 else 0
        is_peak_hour = 1 if hour in [10, 11, 14, 15] else 0
        
        # Seasonal features
        is_summer = 1 if month in [6, 7, 8] else 0
        is_winter = 1 if month in [12, 1, 2] else 0
        
        # Normalize capacity using training value
        capacity_normalized = max_capacity / self.max_capacity_for_normalization
        
        # Return features in EXACT order as feature_names
        features = {
            'day_of_week': day_of_week,
            'is_weekend': is_weekend,
            'month': month,
            'hour': hour,
            'is_morning': is_morning,
            'is_afternoon': is_afternoon,
            'is_evening': is_evening,
            'is_business_hours': is_business_hours,
            'is_peak_hour': is_peak_hour,
            'is_summer': is_summer,
            'is_winter': is_winter,
            'event_id': event_id,
            'max_capacity': max_capacity,
            'duration_minutes': duration_minutes,
            'capacity_normalized': capacity_normalized
        }
        
        return features
    
    def predict_slot_demand(self, slot_info):
        """
        Predict booking demand for a time slot
        
        Args:
            slot_info: Dict with keys: event_id, start_time, max_capacity, duration_minutes
        
        Returns:
            Dict with probability, demand_level, and recommendation
        """
        
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() or load_model() first.")
        
        # Create features
        features = self.create_prediction_features(slot_info)
        
        # Verify all features present
        missing = set(self.feature_names) - set(features.keys())
        if missing:
            raise ValueError(f"Missing required features: {missing}")
        
        # Create feature array in exact order
        X = np.array([[features[col] for col in self.feature_names]], dtype=np.float64)
        
        # Scale features
        X_scaled = self.scaler.transform(X)
        
        # Predict probability
        probabilities = self.model.predict_proba(X_scaled)
        probability = float(probabilities[0][1])  # P(booking)
        
        # Determine demand level based on probability
        if probability >= 0.70:
            demand_level = "High"
            recommendation = "🔥 High Demand - Book Early!"
        elif probability >= 0.45:
            demand_level = "Medium"
            recommendation = "⭐ Popular Time - Book Soon"
        else:
            demand_level = "Low"
            recommendation = "✓ Good Availability"
        
        return {
            'probability': round(probability, 4),
            'demand_level': demand_level,
            'is_recommended': probability >= 0.5,
            'recommendation': recommendation,
            'confidence': float(max(probabilities[0])),
            'demand_score': int(probability * 100),  # 0-100 for sorting
            'model_type': self.model_type
        }
    
    def save_model(self):
        """Save trained model, scaler, and metadata"""
        
        if not self.is_trained:
            raise ValueError("No trained model to save")
        
        # Save model and scaler
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        
        # Save metadata
        metadata = {
            'feature_names': self.feature_names,
            'max_capacity_for_normalization': self.max_capacity_for_normalization,
            'model_type': self.model_type,
            'saved_at': datetime.now().isoformat()
        }
        joblib.dump(metadata, self.metadata_path)
        
        print(f"\n✓ Model saved to: {self.model_path}")
        print(f"✓ Scaler saved to: {self.scaler_path}")
        print(f"✓ Metadata saved to: {self.metadata_path}")
    
    def load_model(self):
        """Load trained model, scaler, and metadata"""
        
        # Check if files exist
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Model file not found: {self.model_path}\n"
                f"Train the model first using /ai/train-models endpoint"
            )
        
        if not os.path.exists(self.scaler_path):
            raise FileNotFoundError(f"Scaler file not found: {self.scaler_path}")
        
        # Load model and scaler
        self.model = joblib.load(self.model_path)
        self.scaler = joblib.load(self.scaler_path)
        
        # Load metadata if available
        if os.path.exists(self.metadata_path):
            metadata = joblib.load(self.metadata_path)
            self.feature_names = metadata['feature_names']
            self.max_capacity_for_normalization = metadata.get('max_capacity_for_normalization', 50.0)
        
        self.is_trained = True
        
        print(f"✓ Model loaded from: {self.model_path}")
        print(f"✓ Features: {len(self.feature_names)}")
        print(f"✓ Normalization value: {self.max_capacity_for_normalization}")


def train_all_models():
    """Train and save all model types (wrapper for API)"""
    
    print("="*60)
    print("SmartBookingAI - Training AI Models")
    print("="*60)
    
    results = {}
    model_types = ["random_forest"]  # Can add "gradient_boosting" later
    
    for model_type in model_types:
        try:
            predictor = BookingDemandPredictor(model_type=model_type)
            metrics = predictor.train()
            predictor.save_model()
            results[model_type] = metrics
        except Exception as e:
            print(f"Error training {model_type}: {e}")
            import traceback
            traceback.print_exc()
            results[model_type] = {'error': str(e)}
    
    return results


if __name__ == "__main__":
    """Direct execution for testing"""
    try:
        results = train_all_models()
        print("\n" + "="*60)
        print("TRAINING COMPLETE")
        print("="*60)
        for model, metrics in results.items():
            print(f"\n{model.upper()}:")
            if 'error' in metrics:
                print(f"  ❌ Error: {metrics['error']}")
            else:
                print(f"  ✓ Test Accuracy: {metrics['test_accuracy']:.4f}")
                print(f"  ✓ F1-Score: {metrics['f1_score']:.4f}")
    except Exception as e:
        print(f"❌ Training failed: {e}")
        import traceback
        traceback.print_exc()