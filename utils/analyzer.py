import google.genai as genai
from datetime import datetime, timedelta
import time

# Rate limiting - track last API call
_last_gemini_call = None
_min_interval = 6  # Increased to 6 seconds between calls for safety

def analyze_with_gemini(sheet_data, gemini_api_key):
    """Use Gemini AI to analyze the sheet data"""
    
    global _last_gemini_call
    
    print(f"\n{'='*60}")
    print(f"[ANALYZER] Function called at: {datetime.now().strftime('%H:%M:%S')}")
    
    if not sheet_data:
        return {'status': 'error', 'message': 'No data to analyze'}
    
    # Rate limiting - wait if needed
    if _last_gemini_call:
        time_since_last = time.time() - _last_gemini_call
        print(f"[RATE LIMIT] Time since last call: {time_since_last:.2f}s")
        
        if time_since_last < _min_interval:
            wait_time = _min_interval - time_since_last
            print(f"[RATE LIMIT] WAITING {wait_time:.2f} seconds before making API call...")
            time.sleep(wait_time)
            print(f"[RATE LIMIT] Wait complete. Proceeding...")
    else:
        print(f"[RATE LIMIT] First call - no wait needed")
    
    try:
        # Configure Gemini with new API
        print(f"[GEMINI] Configuring API...")
        client = genai.Client(api_key=gemini_api_key)
        
        # Format the data for Gemini
        headers = sheet_data[0] if sheet_data else []
        rows = sheet_data[1:] if len(sheet_data) > 1 else []
        
        # Create readable format (more concise)
        data_text = "COLUMNS: " + " | ".join(headers) + "\n\n"
        
        for i, row in enumerate(rows, 1):
            padded_row = row + [''] * (len(headers) - len(row))
            data_text += f"{i}. " + " | ".join(str(cell) for cell in padded_row) + "\n"
        
        # Get today's date
        today = datetime.now().strftime('%m/%d/%Y')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%m/%d/%Y')
        
        # Optimized prompt - creative and varied language
        prompt = f"""Today: {today} | Yesterday: {yesterday}

CRITICAL CREATIVITY INSTRUCTIONS:
- Use VARIED vocabulary - don't repeat the same words/phrases
- Write NATURALLY like a real person - avoid robotic patterns
- Each email should sound UNIQUE even with similar tasks
- Use SYNONYMS and different sentence structures
- Sound CONVERSATIONAL but professional

Write a daily status email in PAST TENSE using this exact format:

Hi Mr. Castillo,

Please refer below for my status updates today. Attached as well is my daily status updates spreadsheet tracker as well as the link. Let me know if you will have any questions or concerns.

Key highlights:
[3-5 bullets with * - BE CREATIVE with wording:
- Use VARIED past-tense verbs (not just "worked on"): researched, explored, investigated, dove into, examined, looked into, reviewed, analyzed, tested, experimented with, studied, familiarized myself with, got hands-on with, practiced, configured, set up, implemented, built, created, developed, attended, participated in, joined, contributed to, finished, completed, wrapped up, concluded, delivered, accomplished
- Use DIFFERENT sentence structures - vary your patterns
- Be SPECIFIC about what you did - mention tools, features, systems by name
- Mix SHORT and LONG sentences for natural flow
- Use connecting words naturally: which, that, where, to help, in order to, by doing, through
- Avoid generic phrases like "completed task" - describe what you ACTUALLY did
- Each bullet should sound DIFFERENT from the others]

Risk and Issues:
[1-3 bullets with * - BE CREATIVE with wording:
- Vary how you describe problems: encountered, ran into, faced, dealt with, noticed, found, discovered, hit a snag with, experienced difficulty with, struggled with
- Be SPECIFIC about the actual issue - not just "had problems"
- Use different ways to explain challenges
- Keep it real and authentic]

Mitigation Plans:
[1-3 bullets with * - BE CREATIVE with wording:
- Vary your action words: addressed it by, resolved it through, fixed it with, tackled it by, handled it via, solved it using, worked around it by, mitigated it with, coordinated with, reached out to, consulted, discussed with, implemented, applied, utilized
- Match these to the issues above
- Describe WHAT you actually did - be specific]

Action Items:
[HTML table - only include rows where:
 - Status="Completed" AND Actual Date={yesterday}
 - Status="Ongoing"/"In Progress" AND Target Date={today}
 - Status="Not Started" AND Target Date<={today}]

<table style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; margin-top: 10px;">
<thead>
<tr>
<th style="background-color: #373f6b; color: white; border: 1px solid #e0e0e0; padding: 10px; text-align: left; font-size: 9pt; font-weight: bold;">Item #</th>
<th style="background-color: #373f6b; color: white; border: 1px solid #e0e0e0; padding: 10px; text-align: left; font-size: 9pt; font-weight: bold;">Description</th>
<th style="background-color: #373f6b; color: white; border: 1px solid #e0e0e0; padding: 10px; text-align: left; font-size: 9pt; font-weight: bold;">Responsible</th>
<th style="background-color: #373f6b; color: white; border: 1px solid #e0e0e0; padding: 10px; text-align: left; font-size: 9pt; font-weight: bold;">Target Date of Completion</th>
<th style="background-color: #373f6b; color: white; border: 1px solid #e0e0e0; padding: 10px; text-align: left; font-size: 9pt; font-weight: bold;">Actual Date of Completion</th>
<th style="background-color: #373f6b; color: white; border: 1px solid #e0e0e0; padding: 10px; text-align: left; font-size: 9pt; font-weight: bold;">Status</th>
</tr>
</thead>
<tbody>
[rows here - Status colors: Completed=#0f9d58, Ongoing=#4285f4, Not Started=#999999]
</tbody>
</table>

Thank you very much.

Regards,
[Name from Responsible column]

REMEMBER: Make each email UNIQUE by using:
- Different vocabulary (synonyms)
- Varied sentence structures
- Specific details about tasks
- Natural, conversational flow
- Creative descriptions

DATA:
{data_text}"""
        
        # Record the API call time BEFORE making the call
        _last_gemini_call = time.time()
        print(f"[GEMINI] Making API call at: {datetime.now().strftime('%H:%M:%S')}")
        
        # Generate with timeout and retry using new API
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.0-flash-exp',  # Using latest model
                    contents=prompt
                )
                
                print(f"[GEMINI] ✓ Success! Response received")
                print(f"{'='*60}\n")
                return {'status': 'success', 'content': response.text}
                
            except Exception as retry_error:
                error_str = str(retry_error).lower()
                print(f"[GEMINI] Attempt {attempt + 1}/{max_retries} failed: {str(retry_error)[:100]}")
                
                if attempt < max_retries - 1 and ('quota' in error_str or 'rate' in error_str or '429' in error_str):
                    # Wait 10 seconds and retry once
                    print(f"[RETRY] Rate limit detected. Waiting 10 seconds before retry...")
                    time.sleep(10)
                    continue
                else:
                    raise retry_error
        
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] {error_msg}")
        print(f"{'='*60}\n")
        
        # Better error messages
        if 'API_KEY' in error_msg or 'invalid' in error_msg.lower():
            return {'status': 'error', 'message': 'Invalid Gemini API key. Please check your key.'}
        elif 'quota' in error_msg.lower() or 'rate' in error_msg.lower() or '429' in error_msg.lower():
            return {
                'status': 'error', 
                'message': f'RATE LIMIT: Please wait 90 seconds before trying again. Free tier = 15 requests/minute. Try using a PAID API key or wait longer between requests.'
            }
        elif 'timeout' in error_msg.lower():
            return {'status': 'error', 'message': 'Request timeout. Please try again.'}
        else:
            return {'status': 'error', 'message': f'Gemini error: {error_msg[:300]}'}