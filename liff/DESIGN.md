# LIFF UI Design System

> Design specification for a mobile-first LINE LIFF application.

## 1. Design Goals

The interface should feel:

- simple and fast to understand
- mobile-first
- friendly but not childish
- visually clean
- easy to use inside the LINE in-app browser
- consistent across every page
- accessible with clear contrast, large touch targets, and readable typography

Primary design direction: **Soft Blue / Clean Minimal**

---

## 2. Color Palette

Use the supplied palette as the core brand colors.

| Token | Hex | Suggested role |
|---|---:|---|
| `--navy-700` | `#293681` | Primary dark, headers, active navigation, important text |
| `--blue-500` | `#4274D9` | Primary action, buttons, links, selected states |
| `--sky-300` | `#95CCDD` | Secondary UI, info backgrounds, chips, decorative accents |
| `--mint-100` | `#D0E7E6` | Soft surfaces, page sections, neutral highlights |

Supporting colors:

| Token | Hex | Role |
|---|---:|---|
| `--white` | `#FFFFFF` | Main surface |
| `--surface` | `#F7F9FC` | App background |
| `--text-primary` | `#172033` | Main text |
| `--text-secondary` | `#657086` | Secondary text |
| `--border` | `#E4E9F0` | Borders / dividers |
| `--success` | `#2E9F6B` | Success |
| `--warning` | `#D99A2B` | Warning |
| `--danger` | `#D84A4A` | Error / destructive actions |

### Color usage rules

- Use `#4274D9` for the main CTA.
- Use `#293681` for titles, strong emphasis, and selected navigation.
- Use `#95CCDD` for light supporting elements, badges, icons, and informational cards.
- Use `#D0E7E6` for subtle sections and low-priority surfaces.
- Avoid filling the entire screen with dark navy.
- Use white or `#F7F9FC` as the dominant screen background.
- Use only one strong primary CTA per screen whenever possible.

---

## 3. Typography

Primary font:

```css
font-family: "Google Sans", "Google Sans Text", "Noto Sans Thai",
             "Noto Sans", system-ui, -apple-system, BlinkMacSystemFont,
             "Segoe UI", sans-serif;
```

> If Google Sans is unavailable in the deployment environment, use `Noto Sans Thai` and system sans-serif fallbacks.

### Type scale

| Style | Size | Weight | Line height | Use |
|---|---:|---:|---:|---|
| Display | 32px | 700 | 1.20 | Rare hero heading |
| H1 | 28px | 700 | 1.25 | Main page title |
| H2 | 22px | 700 | 1.30 | Section title |
| H3 | 18px | 600 | 1.35 | Card title |
| Body Large | 17px | 400 | 1.55 | Important body copy |
| Body | 15px | 400 | 1.55 | Main text |
| Small | 13px | 400 | 1.45 | Metadata |
| Label | 13px | 600 | 1.30 | Input/button labels |

Thai text should not use overly tight line-height.

Recommended:

```css
letter-spacing: 0;
line-height: 1.5;
```

---

## 4. Layout

### Mobile-first

Target LIFF viewport first.

```txt
Minimum supported width: 320px
Primary design width: 360–430px
Tablet / desktop max content width: 720px
```

Main container:

```css
.app-container {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  padding: 16px;
}
```

### Spacing scale

Use an 8px-based spacing system.

```txt
4px   = xs
8px   = sm
12px  = sm+
16px  = md
24px  = lg
32px  = xl
48px  = 2xl
64px  = 3xl
```

Default horizontal page padding:

```txt
Mobile: 16px
Large mobile / tablet: 20–24px
```

Avoid placing important actions directly against the viewport edge.

---

## 5. Border Radius

Rounded interfaces are encouraged, but keep the hierarchy consistent.

```txt
Small controls: 10px
Inputs: 12px
Buttons: 14px
Cards: 18px
Large panels / sheets: 24px
Pills / chips: 999px
```

CSS tokens:

```css
--radius-sm: 10px;
--radius-md: 12px;
--radius-button: 14px;
--radius-card: 18px;
--radius-panel: 24px;
--radius-pill: 999px;
```

Avoid mixing too many different radii on the same screen.

---

## 6. Elevation

Use shadows sparingly.

### Card

```css
box-shadow:
  0 1px 2px rgba(25, 35, 60, 0.04),
  0 6px 20px rgba(41, 54, 129, 0.06);
```

### Modal / Bottom sheet

```css
box-shadow:
  0 -12px 40px rgba(23, 32, 51, 0.14);
```

Do not use strong floating shadows on every component.

---

## 7. Navigation

For a LIFF app, prefer simple navigation.

### Recommended structure

```txt
Home
├── Main content
├── History / Activity
├── Notifications (optional)
└── Profile / Settings
```

For 3–5 primary destinations, use a bottom navigation bar.

### Bottom navigation

Height:

```txt
64px + safe area
```

Rules:

- 3–5 items maximum
- icon + short label
- active item uses `#293681`
- inactive item uses `#657086`
- active icon may use a very light `#D0E7E6` background
- do not hide important navigation behind a hamburger menu on mobile

Example:

```txt
[ Home ]   [ Activity ]   [ Profile ]
```

---

## 8. App Header

Recommended LIFF header:

```txt
←      Page title                 ···
```

Height: `56px`

Rules:

- use sticky header only when the page is long
- title should remain short
- back button touch area: minimum `44 × 44px`
- avoid duplicating LINE's native UI unnecessarily

Header background:

```css
background: rgba(255, 255, 255, 0.94);
backdrop-filter: blur(12px);
border-bottom: 1px solid #E4E9F0;
```

---

## 9. Buttons

### Primary button

```css
background: #4274D9;
color: #FFFFFF;
border-radius: 14px;
min-height: 48px;
padding: 0 18px;
font-weight: 600;
```

Hover / pressed:

```txt
Hover: slightly darker blue
Pressed: scale to 0.98
Disabled: 45% opacity
```

### Secondary button

```css
background: #EEF3FF;
color: #293681;
```

### Tertiary button

```css
background: transparent;
color: #4274D9;
```

### Destructive button

Use red only for destructive actions.

```css
color: #D84A4A;
```

### Button rules

- Minimum height: `44px`, preferably `48px`
- Primary CTA should normally be full-width on mobile
- Do not place two visually equal primary buttons side-by-side
- Add loading state for network actions
- Disable repeated submissions while loading

---

## 10. Inputs

### Text field

```css
height: 48px;
border: 1px solid #E4E9F0;
border-radius: 12px;
background: #FFFFFF;
padding: 0 14px;
```

Focus state:

```css
border-color: #4274D9;
box-shadow: 0 0 0 3px rgba(66, 116, 217, 0.14);
```

Error state:

```css
border-color: #D84A4A;
```

Rules:

- label stays visible above the input
- placeholder is not a replacement for a label
- validation errors appear below the field
- use correct input types (`email`, `tel`, `number`, etc.)
- avoid long multi-field forms in one screen

Example:

```txt
ชื่อที่แสดง
[ Chayutphong              ]

อีเมล
[ example@email.com        ]

[ บันทึก ]
```

---

## 11. Cards

Default card:

```css
background: #FFFFFF;
border: 1px solid #E9EDF4;
border-radius: 18px;
padding: 16px;
```

Card structure:

```txt
Icon / visual
Title
Supporting text
Optional metadata
Optional action
```

Use cards for:

- task summaries
- recent activity
- AI-generated suggestions
- documents
- profile summaries
- progress states

Avoid putting every small piece of information inside a separate card.

---

## 12. List Items

Recommended for history, notifications, lessons, or documents.

```txt
[icon]  Title
        Supporting text             >
```

Height:

```txt
Minimum: 56px
Comfortable: 64–72px
```

Use dividers only when necessary.

Prefer spacing over heavy borders.

---

## 13. Chips and Badges

Use soft palette colors.

Examples:

```css
.info-chip {
  background: #E7F3F7;
  color: #293681;
}

.primary-chip {
  background: #EEF3FF;
  color: #4274D9;
}
```

Use for:

- status
- category
- subject
- filter
- short metadata

Avoid long sentences inside chips.

---

## 14. Status Feedback

Every asynchronous action should visibly communicate state.

### Loading

Prefer skeleton UI for content areas.

Use spinner for:

- button submission
- very short waits
- small isolated components

### Success

```txt
✓ บันทึกเรียบร้อย
```

Use subtle green feedback.

### Error

```txt
ไม่สามารถโหลดข้อมูลได้
[ ลองอีกครั้ง ]
```

Always provide a recovery action when possible.

### Empty state

Example:

```txt
ยังไม่มีประวัติการใช้งาน

เมื่อคุณเริ่มใช้งาน รายการล่าสุดจะแสดงที่นี่

[ เริ่มใช้งาน ]
```

---

## 15. Modal and Bottom Sheet

Prefer bottom sheets over centered modals on mobile.

Use bottom sheet for:

- action menus
- filters
- confirmation
- selecting options
- short forms

Style:

```css
border-radius: 24px 24px 0 0;
padding: 20px 16px;
```

Always support safe-area padding.

---

## 16. Toast

Use for lightweight non-blocking feedback.

Position:

```txt
Top center or bottom above navigation
```

Duration:

```txt
2.5–4 seconds
```

Do not use toast for critical errors requiring action.

---

## 17. Iconography

Recommended icon style:

- rounded outline icons
- consistent stroke width
- 20–24px
- avoid mixing filled, outlined, and 3D icons

Use icons to support labels, not replace unclear actions.

Good:

```txt
🔍 ค้นหา
```

Better in production:

```txt
[search icon] ค้นหา
```

---

## 18. Accessibility

Required minimums:

- touch target: `44 × 44px`
- body text: preferably `15–16px`
- avoid text smaller than `12px`
- visible keyboard focus
- do not rely on color alone for status
- use semantic HTML
- buttons use `<button>`
- navigation uses `<nav>`
- inputs use associated `<label>`
- images use meaningful `alt`
- ensure reasonable contrast

For destructive confirmations:

```txt
ลบบัญชีนี้หรือไม่?

การดำเนินการนี้ไม่สามารถย้อนกลับได้

[ ยกเลิก ]   [ ลบบัญชี ]
```

---

## 19. LIFF-specific UX Rules

### Authentication

If login is required:

```txt
App opens
↓
Check LIFF login
↓
If not logged in → LINE Login
↓
Fetch profile
↓
Show app
```

Do not show a full blank page while checking authentication.

Use:

```txt
กำลังเข้าสู่ระบบ...
```

with a small loading indicator.

### LINE Profile

When profile data is available, keep identity UI compact.

Example:

```txt
[avatar] Chayutphong
         เชื่อมต่อกับ LINE แล้ว
```

### In-app browser

Account for:

- small vertical viewport
- software keyboard
- safe areas
- browser back behavior
- slower mobile network
- touch interaction
- LIFF lifecycle

Avoid:

- tiny controls
- hover-only interaction
- fixed heights for full pages
- important content at the very bottom without safe-area spacing

Use:

```css
min-height: 100dvh;
padding-bottom: env(safe-area-inset-bottom);
```

---

## 20. Recommended Screen Shell

```txt
┌─────────────────────────┐
│ Header                  │
├─────────────────────────┤
│                         │
│ Main content            │
│                         │
│ Cards / Lists / Forms   │
│                         │
│                         │
├─────────────────────────┤
│ Bottom navigation       │
└─────────────────────────┘
```

CSS concept:

```css
.app {
  min-height: 100dvh;
  background: #F7F9FC;
  color: #172033;
}

.main {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  padding:
    16px
    16px
    calc(88px + env(safe-area-inset-bottom));
}
```

---

## 21. Homepage Pattern

Recommended home screen:

```txt
Hello / user summary

Main action card

Quick actions

Recent activity

Optional learning / AI recommendation

Bottom navigation
```

Example:

```txt
สวัสดี Chayut

วันนี้ต้องการทำอะไร?

[ ถาม AI ]
[ เปิดเอกสาร ]
[ ดูประวัติ ]

ล่าสุด
────────────────────
คณิตศาสตร์ • 10 นาทีที่แล้ว
สรุปเรื่องเมทริกซ์
```

---

## 22. Profile Screen Pattern

```txt
[avatar]
Name
LINE connection status

บัญชี
- ข้อมูลส่วนตัว
- การตั้งค่า

แอป
- ภาษา
- การแจ้งเตือน
- เกี่ยวกับ

[ ออกจากระบบ ]
```

Do not place destructive actions near frequently tapped controls.

---

## 23. Form Pattern

Keep forms short.

Preferred:

```txt
Section title

Label
Input

Label
Input

Optional helper text

[ Save ]
```

For long onboarding flows, use multiple short steps instead of one very long form.

Example progress:

```txt
ขั้นตอน 2 จาก 4
████████░░░░░░
```

---

## 24. AI / Chat UI

If the LIFF app includes AI chat:

User message:

```css
background: #4274D9;
color: white;
border-radius: 18px 18px 4px 18px;
```

Assistant message:

```css
background: #FFFFFF;
color: #172033;
border: 1px solid #E9EDF4;
border-radius: 18px 18px 18px 4px;
```

Chat composer:

```txt
[ พิมพ์ข้อความ...                    ][↑]
```

Rules:

- composer stays above keyboard
- send button minimum 44px
- support multiline input
- display sending/error states
- do not auto-scroll if the user is reading older messages
- provide retry when sending fails

---

## 25. Design Tokens

```css
:root {
  /* Brand */
  --navy-700: #293681;
  --blue-500: #4274D9;
  --sky-300: #95CCDD;
  --mint-100: #D0E7E6;

  /* Surface */
  --background: #F7F9FC;
  --surface: #FFFFFF;
  --surface-soft: #F0F6F8;

  /* Text */
  --text-primary: #172033;
  --text-secondary: #657086;
  --text-on-primary: #FFFFFF;

  /* Border */
  --border: #E4E9F0;
  --border-soft: #EEF1F5;

  /* State */
  --success: #2E9F6B;
  --warning: #D99A2B;
  --danger: #D84A4A;

  /* Radius */
  --radius-sm: 10px;
  --radius-md: 12px;
  --radius-button: 14px;
  --radius-card: 18px;
  --radius-panel: 24px;
  --radius-pill: 999px;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;

  /* Typography */
  --font-sans: "Google Sans", "Google Sans Text", "Noto Sans Thai",
               "Noto Sans", system-ui, -apple-system, BlinkMacSystemFont,
               "Segoe UI", sans-serif;
}
```

---

## 26. Tailwind Mapping

If Tailwind CSS is used:

```ts
colors: {
  brand: {
    navy: "#293681",
    blue: "#4274D9",
    sky: "#95CCDD",
    mint: "#D0E7E6",
  },
}
```

Recommended component classes:

```txt
Page background:
bg-[#F7F9FC]

Primary text:
text-[#172033]

Secondary text:
text-[#657086]

Primary button:
bg-[#4274D9] text-white rounded-[14px] min-h-12

Card:
bg-white border border-[#E9EDF4] rounded-[18px] p-4

Input:
h-12 rounded-xl border border-[#E4E9F0] bg-white px-3.5
focus:border-[#4274D9]
```

---

## 27. Component Inventory

Create reusable components rather than styling each screen independently.

Recommended:

```txt
components/
├── layout/
│   ├── AppShell
│   ├── AppHeader
│   ├── BottomNav
│   └── PageContainer
│
├── ui/
│   ├── Button
│   ├── IconButton
│   ├── Card
│   ├── Input
│   ├── Textarea
│   ├── Select
│   ├── Checkbox
│   ├── Radio
│   ├── Switch
│   ├── Badge
│   ├── Avatar
│   ├── Divider
│   ├── Skeleton
│   ├── Spinner
│   ├── Toast
│   ├── Modal
│   └── BottomSheet
│
├── feedback/
│   ├── EmptyState
│   ├── ErrorState
│   └── LoadingState
│
└── line/
    ├── LineProfile
    └── LiffLoginState
```

---

## 28. Interaction Rules

Animations should be subtle.

Recommended durations:

```txt
Tap / press: 100–150ms
Small transition: 150–200ms
Modal / sheet: 200–280ms
```

Recommended easing:

```css
cubic-bezier(0.2, 0, 0, 1)
```

Do not use long decorative animations that block interaction.

Respect:

```css
@media (prefers-reduced-motion: reduce)
```

---

## 29. Responsive Rules

### 320–430px

- full-width controls
- 16px page padding
- 1-column cards
- bottom navigation

### 431–720px

- 20–24px page padding
- cards may use 2 columns where useful
- keep primary actions easy to reach

### >720px

LIFF should still feel like an app, not stretch indefinitely.

Use centered content:

```css
max-width: 720px;
margin-inline: auto;
```

---

## 30. Design Do / Don't

### Do

- one clear primary action per screen
- large touch targets
- short labels
- clear loading states
- clear error recovery
- strong content hierarchy
- soft rounded cards
- consistent spacing
- keep navigation predictable

### Don't

- use more than 2–3 accent colors in one screen
- put every section inside a card
- use excessive gradients
- use heavy glassmorphism
- use tiny text
- use icon-only actions when meaning is unclear
- hide important actions behind multiple taps
- make the user re-enter data already available from LINE
- use desktop-style sidebars as the main navigation inside LIFF

---

## 31. Suggested Visual Style

Overall visual direction:

```txt
Clean Minimal
+
Soft Rounded UI
+
LINE-friendly Mobile UX
+
Blue-centric brand palette
```

Recommended balance:

```txt
60% White / neutral surfaces
20% Very light blue / mint surfaces
15% Navy text and structural elements
5% Strong blue CTA / selected state
```

This keeps the supplied palette visible without making the interface too saturated.

---

## 32. Example Main Card

```html
<section class="feature-card">
  <div class="feature-icon"></div>

  <div>
    <h2>ถาม AI</h2>
    <p>ถามคำถามหรือให้ AI ช่วยสรุปบทเรียน</p>
  </div>

  <button>เริ่มใช้งาน</button>
</section>
```

Suggested visual treatment:

```css
.feature-card {
  background: #FFFFFF;
  border: 1px solid #E9EDF4;
  border-radius: 18px;
  padding: 18px;
}

.feature-card button {
  width: 100%;
  min-height: 48px;
  margin-top: 16px;
  border: 0;
  border-radius: 14px;
  background: #4274D9;
  color: #FFFFFF;
  font: inherit;
  font-weight: 600;
}
```

---

## 33. Base Page CSS

```css
html {
  background: #F7F9FC;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100dvh;

  font-family:
    "Google Sans",
    "Google Sans Text",
    "Noto Sans Thai",
    "Noto Sans",
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;

  color: #172033;
  background: #F7F9FC;

  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

button,
input,
textarea,
select {
  font: inherit;
}

button,
a {
  -webkit-tap-highlight-color: transparent;
}

* {
  box-sizing: border-box;
}
```