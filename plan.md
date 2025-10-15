# RefundRaja — Teaching & Implementation Plan

## Philosophy: Design First, Code Second

We'll understand **what** we're building and **why** before writing code. You'll type all code yourself to learn Django/Python syntax hands-on.

---

## Phase 1: Understanding the Application (Day 1-2)

### What Are We Building?

**RefundRaja** helps users track return/warranty deadlines from online orders by:

1. Receiving order receipt emails (forwarded or from Gmail)
2. Extracting key info: merchant, order date, delivery date, amount, return window
3. Computing deadlines (e.g., 30 days from delivery)
4. Sending reminders before deadlines expire

**MVP Core Features:**

- Store orders manually (user can add order details via form)
- Auto-parse receipts from email text
- Calculate return deadlines
- Send email reminders

**What We're NOT Building in MVP:**

- React frontend (simple Django templates only)
- Mobile app
- Complex ML/AI parsing (start with regex)
- Payment tracking
- Multi-language support

---

### Why Django?

**Key advantages for this project:**

- **Admin panel** (free UI to manage data during development)
- **ORM** (write Python instead of SQL)
- **Auth system** (user accounts built-in)
- **Migrations** (track database schema changes)
- **DRF** (later: build APIs for React frontend)

**Trade-off:** More structure/files than Flask, but saves time on auth/admin/DB.

---

### Application Architecture Overview

```
User → Email Receipt → Parser → Order Model → Deadline Calculator → Reminder Scheduler → Notification
```

**Data Flow:**

1. Email arrives (RawEmail stored)
2. Parser extracts fields → creates Order
3. Order model computes `return_deadline` = delivery_date + return_window_days
4. Celery task checks daily for upcoming deadlines → sends email

---

## Phase 2: Schema Design (Day 2-3)

### Core Entities & Their Relationships

**Teaching Focus:** Understand database relationships (OneToMany, ManyToOne) and field types.

#### Entity 1: User

- **Purpose:** Track who owns which orders
- **Django provides:** Built-in `User` model (username, email, password)
- **Relationship:** One user → Many orders

#### Entity 2: RawEmail

- **Purpose:** Store original email for debugging/re-parsing
- **Fields:**
  - `user` (ForeignKey → User) - who received this
  - `message_id` (unique string) - prevent duplicates
  - `subject`, `from_email`, `received_at` (metadata)
  - `raw_html`, `raw_text` (email body)
  - `attachments` (JSON or separate table later)
- **Relationship:** One RawEmail → One Order (initially; later could be Many)

#### Entity 3: MerchantRule

- **Purpose:** Store default return policies per merchant
- **Fields:**
  - `merchant_name` (CharField) - "Amazon", "Flipkart"
  - `default_return_days` (IntegerField) - 30, 7, etc.
  - `notes` (TextField) - "Electronics have 10 days"
- **Relationship:** Referenced by Order to compute defaults
- **Why separate table?** Different merchants have different policies; easier to update in one place

#### Entity 4: Order

- **Purpose:** The core entity - parsed order details
- **Fields:**
  - `user` (ForeignKey → User)
  - `raw_email` (ForeignKey → RawEmail, nullable) - link to source
  - `merchant_name` (CharField)
  - `order_id` (CharField) - merchant's order ID
  - `order_date` (DateField)
  - `delivery_date` (DateField, nullable)
  - `amount` (DecimalField)
  - `currency` (CharField) - "INR", "USD"
  - `return_window_days` (IntegerField) - 30
  - `return_deadline` (DateField) - **computed field**
  - `warranty_expiry` (DateField, nullable)
  - `parsed_confidence` (FloatField) - 0.0 to 1.0
  - `needs_review` (BooleanField) - flag for low confidence
  - `parsed_json` (JSONField) - store all raw extracted data
- **Relationship:** One Order → Many Notifications

#### Entity 5: Notification

- **Purpose:** Track scheduled and sent reminders
- **Fields:**
  - `user` (ForeignKey → User)
  - `order` (ForeignKey → Order)
  - `notification_type` (CharField) - "return_reminder", "warranty_reminder"
  - `scheduled_at` (DateTimeField)
  - `sent_at` (DateTimeField, nullable)
  - `status` (CharField) - "pending", "sent", "failed"
  - `channel` (CharField) - "email", "web_push" (later)
- **Relationship:** Many Notifications → One Order

---

### Database Relationships Diagram

```
User (1) ←──────── (Many) Order
                      ↓
                  (Many) Notification

RawEmail (1) ──→ (1) Order

MerchantRule (reference) ──→ Order (merchant_name lookup)
```

**Key Concepts:**

- **ForeignKey** = "belongs to one" (Order belongs to one User)
- **reverse relationship** = User can access `user.orders.all()`
- **nullable ForeignKey** = Order might not have a RawEmail (manual entry)

---

## Phase 3: Django Fundamentals (Day 3-5)

### Lesson 1: Django Project Structure

**Teach:**

- **Project** vs **App** concept
  - Project = entire website (RefundRaja)
  - App = reusable module (orders, accounts, parser)
- **settings.py** = configuration (database, installed apps)
- **urls.py** = routing (map URLs to views)
- **manage.py** = CLI tool (run server, migrations)

**Apps we'll create:**

- `accounts` - user auth (later: Google OAuth)
- `orders` - Order model, views, admin
- `ingestion` - RawEmail model, email receiving
- `parser` - parsing logic (regex, dateparser)
- `notifications` - Notification model, Celery tasks
- `merchants` - MerchantRule model

---

### Lesson 2: Models & ORM

**Teach:**

- **Model** = Python class → database table
- **Field types:**
  - `CharField(max_length=100)` - short text
  - `TextField()` - long text
  - `DateField()` / `DateTimeField()` - dates
  - `DecimalField(max_digits=10, decimal_places=2)` - money
  - `IntegerField()` - numbers
  - `BooleanField()` - true/false
  - `JSONField()` - store dicts/lists
  - `ForeignKey(Model, on_delete=CASCADE)` - relationship
- **Migrations** = track schema changes (like git for database)

**Practice:**

- Define `Order` model with all fields
- Run `makemigrations` → creates migration file
- Run `migrate` → applies to database
- Understand `on_delete=CASCADE` (delete order if user deleted)

---

### Lesson 3: Django Admin

**Teach:**

- **Admin panel** = auto-generated UI for CRUD operations
- Register model: `admin.site.register(Order)`
- Customize: `list_display`, `search_fields`, `list_filter`

**Practice:**

- Create superuser: `python manage.py createsuperuser`
- Register Order model
- Add custom display: show order_id, merchant, deadline in list

---

### Lesson 4: Views & URLs

**Teach:**

- **View** = function/class that handles HTTP request → returns response
- **Template** = HTML with placeholders `{{ order.merchant_name }}`
- **URL routing** = map `/orders/` → view function

**Types:**

- **Function-based view (FBV):** Simple function
- **Class-based view (CBV):** Reusable (ListView, DetailView)

**Practice:**

- Create `OrderListView` (show all orders)
- Create `OrderDetailView` (show one order)
- Wire URLs: `/orders/` → list, `/orders/123/` → detail

---

### Lesson 5: Django REST Framework (DRF)

**Teach:**

- **Serializer** = convert Model ↔ JSON
- **ViewSet** = API endpoints (list, create, retrieve, update, delete)
- **Router** = auto-generate URLs for API

**Practice:**

- Create `OrderSerializer`
- Create `OrderViewSet`
- Test API: `GET /api/orders/`, `POST /api/orders/`

---

## Phase 4: Core Features Implementation (Day 6-15)

### Feature 1: Manual Order Entry

**Goal:** User can add order via form

**Steps:**

1. Create Order model
2. Create Django form (ModelForm)
3. Create view to handle form submission
4. Create template with HTML form
5. Test: add order via browser

**Teaching:** Forms, validation, POST handling

---

### Feature 2: Email Ingestion

**Goal:** Store raw email text

**Steps:**

1. Create RawEmail model
2. Create API endpoint to POST email (simulate receiving)
3. Save email body and metadata
4. Link RawEmail → Order (nullable initially)

**Teaching:** API design, JSON requests, database writes

---

### Feature 3: Parser (Regex-Based)

**Goal:** Extract order details from email text

**Steps:**

1. Write regex patterns for:
   - Order ID: `Order #123-456`
   - Dates: `Delivered on 10 Oct 2025`
   - Amount: `₹1,299.00`
   - Merchant: `from: noreply@amazon.in`

2. Use `dateparser` library for date parsing
3. Create `parse_email(raw_text)` function → dict
4. Write unit tests with sample emails

**Teaching:** Regex, string manipulation, testing

---

### Feature 4: Deadline Calculation

**Goal:** Compute `return_deadline` from delivery date + return window

**Steps:**

1. Add method to Order model:

   ```python
   def calculate_return_deadline(self):
       if self.delivery_date and self.return_window_days:
           return self.delivery_date + timedelta(days=self.return_window_days)
   ```

2. Auto-populate on save (override `save()` method)
3. Display in admin and detail view

**Teaching:** Model methods, datetime arithmetic, `save()` override

---

### Feature 5: Merchant Rules

**Goal:** Lookup default return days by merchant

**Steps:**

1. Create MerchantRule model
2. Pre-populate with common merchants (Amazon=30, Flipkart=7)
3. In parser, lookup merchant → get default return days
4. Use as fallback if not found in email

**Teaching:** Database queries, `get_or_create()`, defaults

---

### Feature 6: Celery Background Tasks

**Goal:** Run parsing in background (don't block web request)

**Steps:**

1. Install Celery + Redis
2. Create `tasks.py`: `parse_raw_email(raw_email_id)`
3. Trigger task when RawEmail created
4. Task creates Order after parsing

**Teaching:** Async tasks, task queues, idempotency

---

### Feature 7: Reminder Scheduler

**Goal:** Send email 7/3/1 days before deadline

**Steps:**

1. Create Notification model
2. Celery periodic task (daily check):
   - Find orders with deadline in 7/3/1 days
   - Create Notification if not exists

3. Send email (Django `send_mail`)
4. Mark Notification as sent

**Teaching:** Periodic tasks, email sending, querying with filters

---

### Feature 8: User Feedback Loop

**Goal:** User can edit parsed fields if wrong

**Steps:**

1. Add `needs_review` flag to Order
2. Show "Review" button if flag = True
3. Create edit form (pre-filled with parsed data)
4. User submits corrections → update Order

**Teaching:** Update views, forms with initial data

---

## Phase 5: Python Concepts (Integrated Throughout)

### Tuples vs Lists

- **Tuple:** Immutable, fixed size `coords = (12.97, 77.59)`
- **List:** Mutable, dynamic `items = ['pen', 'book']`
- **When:** Use tuple for fixed records (lat/lng), list for collections

### Dicts & .get()

- **Dict:** Key-value pairs `order = {'id': '123', 'amount': 899}`
- **Safe access:** `order.get('delivery_date', None)` (no KeyError)
- **When:** Parsing returns dict, database returns model

### List Comprehensions

- **Syntax:** `[expr for item in list if condition]`
- **Example:** `amounts = [float(x) for x in raw_amounts if x.isdigit()]`
- **When:** Transforming/filtering lists (common in parsing)

### Datetime Parsing

- **Library:** `dateparser.parse("10 Oct 2025")` → `datetime` object
- **Arithmetic:** `deadline = delivery + timedelta(days=30)`
- **Formatting:** `deadline.strftime("%d %b %Y")`

### Regex Basics

- **Pattern:** `r'Order\s*#\s*([A-Z0-9\-]+)'`
- **Extract:** `match = re.search(pattern, text); match.group(1)`
- **When:** Extracting structured data from unstructured text

---

## Phase 6: Testing & Best Practices (Day 16-18)

### Unit Tests

- Test parser functions with sample emails
- Test model methods (deadline calculation)
- Test API endpoints (create order, list orders)

### Code Organization

- **Thin views:** Move logic to services/utils
- **Parser module:** Separate file for parsing logic
- **DRY:** Don't repeat regex patterns, use constants

### Error Handling

- Try/except for parsing failures
- Fallback values (if no delivery date, use order date + 3 days)
- Log errors for debugging

---

## Success Metrics

**After completing this plan, you will:**

1. Understand Django project structure and MVT pattern
2. Design normalized database schemas with relationships
3. Build REST APIs with DRF
4. Write background tasks with Celery
5. Parse unstructured text with regex and libraries
6. Deploy a working MVP without infrastructure complexity

**Next Steps (Post-Plan):**

- Add Docker for deployment
- Add Google OAuth
- Add React frontend with shadcn
- Add LLM fallback for parsing
