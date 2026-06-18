# 📖 Complete User Guide: Jewelry Billing & Dual Ledger System

Welcome to your custom jewelry management suite. This system is designed to handle the unique challenges of the jewelry trade, specifically the **Dual Ledger**—tracking both physical gold weight (Grams/Pure) and currency (Cash) simultaneously.

Here is a breakdown of every feature, automatic calculation, and shortcut built into your system.

---

## 1. Creating a Bill (The Header)

When you start a new bill, the system sets up the foundation for all your calculations.

- **Customer & Date:** You select the customer and the date.
- **Daily Gold Rates:** The system automatically pulls today’s gold rates (24K, 22K, and 18K) from your main settings.
- **Looping Bill Numbers (Automation):**
- _How it works:_ The system automatically assigns a bill number, but it loops from 1 to 25. Once you hit Bill #25, the next bill starts back at #1.
- _The Benefit:_ This mimics traditional, short physical estimate books, making it easy to track daily rough estimates without numbers getting too long or confusing.

---

## 2. Adding Jewelry to the Bill (Line Items)

This is where you add the actual items the customer is buying. The system is packed with automatic calculators here so your staff doesn't have to use a handheld calculator.

### **Type & Melting (Automation)**

- _How it works:_ When you choose the gold type (either `22K` or `18K`), the system automatically fills in the standard "Melting" purity percentage.
- If `22K` is selected → Melting becomes `92.0`
- If `18K` is selected → Melting becomes `76.0`

- _The Benefit:_ Saves time and prevents staff from accidentally entering the wrong base purity for standard gold types.

### **Net Weight (Calculation)**

- _How it works:_ It takes the total weight of the item and subtracts any stones, enamel, or non-gold materials (Less).
- _The Math:_ `Net Weight = Weight - Less`
- _The Benefit:_ Ensures you are only charging the customer for the actual precious metal.

### **The "Touch" vs. "VAT" Toggle (Automation & Calculation)**

In the jewelry trade, you might quote a customer using a **VAT %** (Value Added / Making Charge percentage) OR by quoting the final **Touch** (Total billed purity). These two fields are magically linked.

- _How it works:_
- If you type in a **VAT** percentage, the system instantly calculates the **Touch**.
- If you type in the **Touch**, the system works backward to calculate the **VAT**.

- _The Math (for 22K):_
- `Touch = (VAT + 100) x (22 ÷ 24)`
- `VAT = (Touch x 24 ÷ 22) - 100`

- _The Benefit:_ Ultimate flexibility for your salespeople. They can negotiate with the customer using whichever method the customer prefers, and the software handles the complex conversion instantly.

### **Total Weight & Pure Gold (Calculation)**

- _Total Wt:_ This adds the making charges (VAT) to the physical weight.
- _The Math:_ `Total Wt = Net Weight + VAT %`

- _Pure:_ This calculates the absolute 24K pure gold equivalent of the item based on the final Touch.
- _The Math:_ `Pure = Net Weight x (Touch %)`

- _The Benefit:_ Gives you exact figures for inventory deduction and ledger balancing.

### **Final Cash Amount (Calculation)**

- _How it works:_ It takes the billed weight (Total Wt), multiplies it by today's specific Karat rate, and adds any flat extra charges (like hallmark fees or fixed making charges).
- _The Math:_ `Cash = (Total Wt x Daily Karat Rate) + Charges`
- _The Benefit:_ Instantly gives the final retail price for the item without manual math errors.

---

## 3. The Dual Ledger (Transactions & Payments)

Once the items are added, the customer owes you a balance. Because this is a jewelry business, they don't just owe you cash—they might owe you gold, or pay you in old gold. This is handled in the **Transactions** tab.

The system keeps a live, running tally of two things at the bottom of the screen:

1. **Remaining Pure:** How much fine gold the customer owes you.
2. **Remaining Balance:** How much cash the customer owes you.

### **Transaction Types Explained:**

Whenever a customer makes a payment or hands over an item, you log it here. The system automatically updates the running balances based on what you select:

- **Metal Received / Metal Payment:** If the customer gives you pure gold (or you give them some), it calculates the pure weight (`Gross - Less x Purity`) and deducts it from the **Remaining Pure** balance.
- **Cash Received / Cash Payment:** Straightforward cash exchange. Deducts directly from the **Remaining Balance** (Cash).
- **Old Item / Return Item:** If a customer brings in old jewelry, the system figures out its pure gold value.
- _Special Automation:_ For "Old Items", if you enter a cash rate, it will convert that old gold into cash value and deduct it from the customer's cash bill. If you don't enter a rate, it deducts it from their gold bill.

### **The "Rate Cut" Magic (Automation & Calculation)**

A "Rate Cut" is when a customer decides to fix the price of the gold they owe you today, effectively converting their "Gold Debt" into a "Cash Debt".

- **Automation 1: Auto-Fill Weight:** If you select "Rate Cut", the system automatically looks at the customer's exact **Remaining Pure** balance and fills it in. _Benefit: You don't have to memorize or re-type what they owe._
- **Automation 2: Forward Calculation:** If you type in the Rate, it calculates the Cash Amount. (`Amount = Pure Weight x Rate`).
- **Automation 3: Reverse Calculation:** If the customer says, "I only want to cut the rate for ₹50,000," you just type `50,000` into the Amount box. The system will magically work backward to figure out exactly how much gold that covers, or what the rate should be.
- _The Math:_ `Weight = Amount ÷ Rate`

- _The Benefit:_ This is a massive time-saver. It handles the most complicated, error-prone negotiation in the jewelry trade flawlessly and keeps the dual ledgers perfectly balanced.

---

## 4. Printing & Reports

The system offers clean, professional printouts designed to look premium while protecting your business policies.

There are two ways to print a bill:

1. **Print Bill (Rough Estimate):** This prints a standard breakdown of the weights, melting, touch, pure gold, and cash. It is ideal for approvals, B2B, or quoting.
2. **Print Retail Bill:** This prints a slightly different format tailored for final retail customers.

- _Special Automation (GST):_ The Retail Bill automatically calculates and adds a **3% GST** to the final cash total at the very bottom of the page.
- _The Math:_ `Grand Total = Total Cash x 1.03`
- _The Benefit:_ Keeps your on-screen workspace uncluttered from tax calculations while ensuring your printed retail invoices are legally compliant and accurately totaled.

Both printouts automatically include your daily 22K/18K/24K rates, a ledger history if you choose to show it, and a standard policy note: _"No Return / No Exchange After Delivery."_
