# Interactive Shopping List Demo

Demo prototype for an enhanced shopping list interface designed for use while shopping.

## Features

**Interactive Checkboxes:**
- Check off items as you shop
- Checked items fade and show strikethrough
- Visual progress tracking

**Add/Remove Items:**
- Add custom items on the fly
- Remove items you don't need
- Custom items highlighted in separate section

**Category Management:**
- Collapse/expand categories to reduce clutter
- See count of unchecked items per category
- Organize by food type (Dairy, Meat, Vegetable, etc.)

**Progress Stats:**
- Total items counter
- Checked items counter
- Remaining items counter

**Offline Support:**
- Works completely offline with PWA
- State persisted in localStorage
- No server needed while shopping

**Mobile Optimized:**
- Large touch targets for checkboxes
- Responsive layout for small screens
- Full-screen experience when installed as PWA

## Accessing the Demo

```
http://localhost:5000/shopping_demo
```

Or click the **"Demo"** button in navigation.

## How to Use

**Check Off Items:**
- Tap checkbox next to item
- Item fades and shows strikethrough
- Progress stats update automatically

**Add Custom Items:**
1. Type item name in "Add item" field
2. Optionally add quantity
3. Click "Add" or press Enter
4. Item appears in "Custom Items" section

**Remove Items:**
- Click × button next to item
- Confirms before removing

**Category Controls:**
- Click category header to collapse/expand
- "Expand All" / "Collapse All" buttons for quick navigation

**Utility Buttons:**
- "Clear Checked" - Remove all checked items from list
- "Clear All" - Remove entire list
- "Reset Demo" - Restore demo data

## Data Storage

**Demo Mode:**
- Uses sample data (dairy, meat, vegetables, etc.)
- Stored in browser localStorage
- Persists across sessions
- Changes saved automatically

**Production Implementation:**
Would need:
- API to fetch current shopping list
- Sync changes back to server
- Handle concurrent edits
- Offline queue for changes made while offline

## Mobile Usage

**Install as PWA:**
1. Visit demo page
2. Install app to home screen
3. Open from home screen
4. Works offline while shopping

**At the Store:**
- No internet needed
- Check off items as you grab them
- Add forgotten items on the spot
- Track progress through your list

## Technical Details

**Technologies:**
- Vanilla JavaScript (no frameworks)
- localStorage for persistence
- CSS for mobile-responsive design
- Works with existing PWA service worker

**State Management:**
```javascript
{
  "DAIRY": [
    { name: "Milk", quantity: "1 gallon", checked: false }
  ],
  "CUSTOM": [
    { name: "Coffee", quantity: "", checked: false, custom: true }
  ]
}
```

**Persistence:**
- Saved to localStorage on every change
- Key: `shopping_list_demo`
- Survives page refresh and browser restart

## Integration with Real Shopping List

To integrate with actual shopping list:

**1. API Endpoint:**
```python
@app.route("/api/shopping_list")
def get_shopping_list_api():
    selected_slugs = [r.slug for r in get_all_recipes() if r.selected]
    lists, metas = _get_shopping_list_data()
    main, secondary = get_merged_shopping_list(selected_slugs, lists)

    # Format for interactive list
    data = {}
    for category, items in main.items():
        data[category] = [
            {"name": item.food.get_name(),
             "quantity": item.format_quantity(selected_slugs),
             "checked": False}
            for item in items
        ]
    return jsonify(data)
```

**2. Sync Changes:**
- POST checked state back to server
- Store in user session or database
- Support multiple devices

**3. Offline Sync:**
- Queue changes while offline
- Push to server when back online
- Resolve conflicts if needed

## Possible Enhancements

**Smart Features:**
- Remember frequently checked-off items
- Suggest common additions
- Re-order items by store layout
- Share list with family members

**Store Integration:**
- Group by aisle/location
- Store-specific layouts
- Price tracking
- Quantity suggestions based on recipes

**Recipe Integration:**
- Link items back to source recipes
- Show which recipe needs each item
- Adjust quantities on the fly

**Advanced UI:**
- Drag to reorder items
- Swipe to check off
- Dark mode for store lighting
- Voice input for hands-free adding

## Demo vs Production

| Feature | Demo | Production Needed |
|---------|------|-------------------|
| Check off items | ✅ Works | API sync |
| Add custom items | ✅ Works | Save to database |
| Remove items | ✅ Works | Update server |
| Offline support | ✅ Works | Sync queue |
| Category collapse | ✅ Works | Save preference |
| Progress tracking | ✅ Works | - |
| Multiple users | ❌ Local only | User accounts |
| Device sync | ❌ Local only | Cloud storage |

## Next Steps

**Test the Demo:**
1. Start app: `uv run web/app.py`
2. Visit: http://localhost:5000/shopping_demo
3. Try all features
4. Test on mobile (install as PWA)

**Provide Feedback:**
- Is the interface intuitive?
- What features are most useful?
- What's missing or awkward?
- Mobile usability good?

**Implementation Decision:**
- Keep demo data or integrate with real shopping list?
- Add user accounts for sync?
- Keep it simple (local only) or full-featured?

## Files

```
web/
├── app.py                      # Added /shopping_demo route
└── templates/
    └── shopping_demo.html      # Interactive list template
```

Demo is self-contained - doesn't modify existing shopping list functionality.
