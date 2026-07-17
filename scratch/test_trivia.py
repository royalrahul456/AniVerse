import sys
sys.path.append('c:\\Users\\Rahul Pachute\\Downloads\\coding\\AniVerse')

from handlers.games import TRIVIA_QUESTIONS

print("Testing trivia evaluation...")

# Simulate all questions and options
for q_idx, q in enumerate(TRIVIA_QUESTIONS):
    print(f"\nQuestion {q_idx}: {q['q']}")
    for opt_idx, opt in enumerate(q['opts']):
        is_correct = opt_idx == q['ans']
        print(f"  Option {opt_idx}: {opt} -> is_correct: {is_correct} (Expected: {opt_idx == q['ans']})")
