from django.conf import settings
from django.core.management.base import BaseCommand
from accounts.models import VoiceData, User
import os
import numpy as np
import joblib
import io

class Command(BaseCommand):
    help = 'Evaluate and update threshold and margin for user voice models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user_id',
            type=int,
            help='Evaluate threshold for specific user ID',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        if user_id:
            users = User.objects.filter(id=user_id)
        else:
            users = User.objects.all()

        for user in users:
            try:
                vd = VoiceData.objects.get(user=user)
                self.stdout.write(f"Evaluating threshold for user {user.id}...")

                scaler = joblib.load(io.BytesIO(vd.scaler_model))
                gmm = joblib.load(io.BytesIO(vd.gmm_model))

                # Path folder validasi harus disesuaikan
                pos_folder = os.path.join(settings.MEDIA_ROOT, 'voice_train', str(user.id))
                neg_folder = os.path.join(settings.MEDIA_ROOT, 'validation', 'neg', str(user.id))

                if not os.path.exists(pos_folder) or not os.path.exists(neg_folder):
                    self.stdout.write(f"Validation folders missing for user {user.id}, skipping.")
                    continue

                pos_files = [os.path.join(pos_folder, f) for f in os.listdir(pos_folder) if f.endswith('.wav')]
                neg_files = [os.path.join(neg_folder, f) for f in os.listdir(neg_folder) if f.endswith('.wav')]

                if not pos_files or not neg_files:
                    self.stdout.write(f"Insufficient validation data for user {user.id}, skipping.")
                    continue

                def extract_mfcc(file_path):
                    import librosa
                    audio, sr = librosa.load(file_path, sr=None)
                    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=40)
                    return mfcc.T

                def compute_scores(files):
                    scores = []
                    for fpath in files:
                        mfcc = extract_mfcc(fpath)
                        scaled = scaler.transform(mfcc)
                        score = gmm.score(scaled)
                        scores.append(score)
                    return np.array(scores)

                pos_scores = compute_scores(pos_files)
                neg_scores = compute_scores(neg_files)

                all_scores = np.concatenate([pos_scores, neg_scores])
                min_score, max_score = all_scores.min(), all_scores.max()
                thresholds = np.linspace(min_score, max_score, 100)

                best_acc = 0
                best_threshold = vd.threshold
                best_margin = 0.0

                for t in thresholds:
                    tp = np.sum(pos_scores >= t)
                    fn = np.sum(pos_scores < t)
                    tn = np.sum(neg_scores < t)
                    fp = np.sum(neg_scores >= t)

                    far = fp / (fp + tn) if (fp + tn) > 0 else 0
                    frr = fn / (fn + tp) if (fn + tp) > 0 else 0
                    acc = (tp + tn) / (len(pos_scores) + len(neg_scores))

                    margin_candidate = vd.threshold - t

                    if acc > best_acc:
                        best_acc = acc
                        best_threshold = t
                        best_margin = margin_candidate

                vd.threshold = best_threshold
                vd.margin = best_margin
                vd.save()

                self.stdout.write(f"User {user.id} evaluated. Threshold: {best_threshold:.2f}, Margin: {best_margin:.2f}, Accuracy: {best_acc:.3f}")
            except VoiceData.DoesNotExist:
                self.stdout.write(f"User {user.id} has no VoiceData. Skipping.")
            except Exception as e:
                self.stderr.write(f"Error evaluating user {user.id}: {str(e)}")
