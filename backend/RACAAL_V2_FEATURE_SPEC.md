# RACAAL v2 Feature Entitlements and Implementation Notes

## Access policy
- First 7 days after trial activation: all features are available for evaluation.
- After trial: Free features remain available; Premium-only features require an active subscription.
- Free: welcome messages, group rules, photo verification, manual remove/kick, ban/unban, restrict/unrestrict, website-link blocking/removal, normal send-now group messages, and all Bible features.
- Premium: all AI features; scheduled messaging; broadcasting; broadcasts with buttons; comments with buttons; advanced group protection and automated moderation.
- Bible: all features are Free. Module sections: daily test (send now + auto-send settings), Bible questions, quiz rounds, topics/subjects, and Bible books.
- Timezone default: Africa/Kampala (East Africa Time, UTC+3).

## Premium advanced protection feature candidates
1. Anti-flood rate limits and burst detection.
2. Anti-spam repeated-message detection.
3. Link/domain allowlist and denylist automation beyond basic link removal.
4. Scam/phishing URL heuristics and suspicious-domain blocking.
5. CAPTCHA/challenge flows for suspicious new members.
6. Raid/join-spike detection and temporary join lockdown.
7. Auto-mute / auto-restrict escalation rules.
8. Keyword and phrase filters with action severity.
9. Media/file/type restrictions and unsafe attachment controls.
10. Impersonation and repeated username/display-name pattern detection.
11. Account-age and suspicious-new-account heuristics where available.
12. Mention/tag spam and excessive forwarding detection.
13. Duplicate content and copy-paste spam detection.
14. Warning points, timed mutes and escalation ladders.
15. Trusted-member / moderator allowlists and protected roles.
16. Automated blacklist sync and per-group blacklist management.
17. Audit trail, incident summaries and moderation analytics.
18. Configurable slow mode and temporary read-only lockdown.
19. Automatic deletion of service/join spam.
20. Emergency lockdown with admin-only release.

Telegram limitations apply: the bot needs the appropriate admin rights, and Telegram does not expose every signal needed to identify bots, account age, or intent reliably.

## Implementation status notes
This package adds a Bible settings panel, a manual Bible send-now API action, eye-friendly mobile CSS, and sets the default trial duration to seven days. It does not by itself implement every listed protection handler, a complete recurring Bible-test scheduler, subscription payment/renewal integration, or end-to-end plan enforcement in every existing bot command. Those require backend/bot integration and live Telegram tests before production claims.
