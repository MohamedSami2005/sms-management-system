import re

def escape_regex(s):
    return re.escape(s)

def format_personalized_message(text, recipient_name, template_content=""):
    if not text:
        return ""
    cleaned = text
    name = (recipient_name or "").strip()
    tmpl = template_content or ""

    if name:
        escaped_name = escape_regex(name)

        # 1. Deduplicate consecutive identical recipient names (e.g. 'SAQSAQ' -> 'SAQ', 'SAQ SAQ' -> 'SAQ')
        duplicate_name_regex = re.compile(rf'({escaped_name})(?:\s*{escaped_name})+', re.IGNORECASE)
        cleaned = duplicate_name_regex.sub(r'\1', cleaned)

        # 2. Fix inverted or incorrect concatenation with static prefixes/titles (e.g. 'SAQProf' or 'SAQ SAQProf' -> 'Prof. SAQ')
        has_space_in_tmpl = ('Prof. ' in tmpl) or ('Dr. ' in tmpl) or ('Mr. ' in tmpl) or ('Mrs. ' in tmpl) or ('Ms. ' in tmpl) or ('Prof.' not in tmpl)

        inverted_regex = re.compile(rf'\b({escaped_name})\s*(Prof\.?|Dr\.?|Mr\.?|Mrs\.?|Ms\.?)\b', re.IGNORECASE)
        def _fix_inv(match):
            p_name = match.group(1)
            p_prefix = match.group(2).rstrip('.') + '.'
            return f"{p_prefix} {p_name}" if has_space_in_tmpl else f"{p_prefix}{p_name}"

        cleaned = inverted_regex.sub(_fix_inv, cleaned)

        # 3. If recipient name is already present, do not duplicate it if repeated across multiple variables
        all_name_matches = list(re.finditer(rf'\b{escaped_name}\b', cleaned, re.IGNORECASE))
        if len(all_name_matches) > 1:
            first = True
            def _keep_first(m):
                nonlocal first
                if first:
                    first = False
                    return m.group(0)
                return ""
            cleaned = re.sub(rf'\b{escaped_name}\b', _keep_first, cleaned, flags=re.IGNORECASE)

    # 4. Deduplicate duplicated static honorific titles (e.g. 'Prof. Prof.' -> 'Prof.')
    cleaned = re.sub(r'\b(Prof\.|Dr\.|Mr\.|Mrs\.|Ms\.)\s*(?:\1\s*)+', r'\1 ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(Prof|Dr|Mr|Mrs|Ms)\s*(?:\1\s*)+', r'\1 ', cleaned, flags=re.IGNORECASE)

    # Clean up redundant consecutive spaces or dangling commas/spaces
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned).strip()
    return cleaned

assert format_personalized_message('SAQSAQProf', 'SAQ', 'Prof. {#var#}') == 'Prof. SAQ'
assert format_personalized_message('SAQSAQProf', 'SAQ', 'Prof.{#var#}') == 'Prof.SAQ'
assert format_personalized_message('Prof. SAQ', 'SAQ', 'Prof. {#var#}') == 'Prof. SAQ'
assert format_personalized_message('Prof. Prof. SAQ', 'SAQ', 'Prof. {#var#}') == 'Prof. SAQ'
assert format_personalized_message('SAQ SAQ', 'SAQ', '{#var#} {#var#}') == 'SAQ'
assert format_personalized_message('SAQProf', 'SAQ', 'Prof. {#var#}') == 'Prof. SAQ'
assert format_personalized_message('SAQ SAQProf', 'SAQ', 'Prof. {#var#}') == 'Prof. SAQ'
assert format_personalized_message('Prof. SAQ, your fee is received.', 'SAQ', 'Prof. {#var#}, your fee is received.') == 'Prof. SAQ, your fee is received.'
assert format_personalized_message('Dear Prof. SAQSAQ, welcome.', 'SAQ', 'Dear Prof. {#var#}, welcome.') == 'Dear Prof. SAQ, welcome.'
assert format_personalized_message('Dr. Mohamed Sami', 'Mohamed Sami', 'Dr. {#var#}') == 'Dr. Mohamed Sami'
assert format_personalized_message('Hello world', '', '') == 'Hello world'
assert format_personalized_message('', 'SAQ', '') == ''

print("All edge case assertion tests passed successfully!")
