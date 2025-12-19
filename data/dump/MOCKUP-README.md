# Mockup PN-first — Design e Linee Guida

## Panoramica

Questo documento descrive il mockup HTML/CSS per l'interfaccia PN-first di Bike Copilot. Il mockup dimostra un'interfaccia moderna, intuitiva e professionale seguendo i principi UX/UI state-of-the-art.

## File del Mockup

**Posizione**: `mockup-pn-first.html`

Il mockup è un file HTML standalone che può essere aperto direttamente nel browser per visualizzare il design proposto.

## Principi di Design Applicati

### 1. **Design System Coerente**

Il mockup utilizza un design system completo con:
- **Palette colori**: Blu primario (#2563eb), gradazioni di grigio per testo e sfondi, colori semantici (verde per successo, rosso per errori, giallo per avvisi)
- **Spaziatura consistente**: Sistema di spacing basato su multipli di 0.25rem
- **Tipografia**: Font system con fallback universali, dimensioni gerarchiche
- **Border radius**: Arrotondamenti coerenti (small, medium, large)
- **Ombre**: Shadow system a tre livelli per profondità visiva

### 2. **Visual Hierarchy Chiara**

- **Header**: Identifica chiaramente l'applicazione e il suo scopo
- **Search bar**: Prominente in cima, facile da trovare e usare
- **Results**: Layout a card per ogni PN con tabella offerte chiara
- **Cart**: Sticky sulla destra (desktop), sempre visibile
- **CTA buttons**: Colori e posizionamento strategici

### 3. **Mobile-First & Responsive**

- Grid layout che si adatta automaticamente (2 colonne desktop → 1 colonna mobile)
- Touch-friendly button sizes (min 44x44px)
- Flexible input fields e form elements
- Collapsing navigation per schermi piccoli

### 4. **User Experience Ottimizzata**

#### Flusso Principale
1. **Ricerca PN**: Campo input prominente con placeholder esplicativo
2. **Batch input**: Bottone "Incolla Lista" per inserimenti multipli
3. **Filtri visibili**: Dealer selection e opzioni sempre accessibili
4. **Risultati chiari**: Ogni PN mostra tutte le offerte disponibili
5. **Confronto facile**: Tabella con colonne standardizzate (dealer, prezzo, stock, lead time)
6. **Badge informativi**: "Miglior prezzo", "In stock", "24h" per decisioni rapide
7. **Azioni immediate**: Bottone "Aggiungi" per ogni offerta
8. **Cart management**: Controlli qty intuitivi (+/- buttons)
9. **Ottimizzatore**: Scenari pre-definiti con spiegazioni chiare
10. **Quote generation**: Form semplice con campi essenziali

### 5. **Componenti UI Moderni**

#### Cards
- Border radius arrotondati
- Box shadow per profondità
- Hover states per interattività
- Header colorati per differenziazione

#### Tables
- Header con background grigio chiaro
- Sticky header (quando implementato con scroll)
- Zebra striping al hover
- Allineamento consistente

#### Buttons
- Stati chiari (primary, secondary)
- Hover effects con transform e shadow
- Icon + text per chiarezza
- Full-width per azioni importanti

#### Forms
- Labels sempre visibili
- Focus states con outline colorato
- Placeholder text descrittivo
- Validazione inline (da implementare)

#### Badges
- Colori semantici (verde=successo, rosso=errore, giallo=warning, blu=info)
- Pill shape per riconoscibilità
- Icons inline quando appropriato

### 6. **Accessibilità**

- **Contrasto**: Tutti i colori superano WCAG AA (4.5:1 per testo normale)
- **Focus states**: Outline visibili per navigazione da tastiera
- **Semantic HTML**: Uso corretto di header, section, table, form elements
- **Labels**: Tutti gli input hanno label associate
- **Alt text**: Pronto per immagini/icon (da aggiungere)

### 7. **Performance & Scalabilità**

- **CSS puro**: Nessuna dipendenza da framework pesanti
- **Design system**: Variabili CSS per facile manutenzione
- **Componenti riutilizzabili**: Classi modulari per consistency
- **Ottimizzazione**: Minimal DOM nesting, efficient selectors

## Mapping con Requisiti

### REQ-004: Interfaccia PN-first

✅ **Input PN singolo**: Campo input prominente con label chiaro
✅ **Incolla lista**: Bottone dedicato per batch input
✅ **Risultati per PN**: Card separate per ogni part number
✅ **Tabella offerte**: Dealer, prezzo, stock, lead time, azioni
✅ **Evidenze**: Badge "Miglior prezzo", "24h", stock status
✅ **Carrello multi-riga**: Gestione quantità, subtotali, rimozione
✅ **Preventivo**: Form completo con tutti i campi richiesti

### REQ-005: Ottimizzatore d'ordine

✅ **Scenari**: Radio buttons per "Miglior prezzo", "Un solo dealer", "Al massimo N", "Più veloce"
✅ **Parametri**: Input per max N dealer
✅ **Override**: Struttura pronta per blocco dealer per riga (da implementare)
✅ **Ricalcolo**: Bottone dedicato

### REQ-006: Branding preventivi

✅ **Form preventivo**: Cliente, contatto, validità, note
✅ **Output**: Bottone "Crea Preventivo (PDF/HTML)"
✅ **Preparato per**: Logo, intestazione negozio (da collegare a backend)

### ARC-020: Wireframe UX

Il mockup implementa fedelmente il wireframe proposto in ARC-020 con miglioramenti:
- Layout più pulito e moderno
- Tipografia professionale
- Color coding semantico
- Interazioni più intuitive
- Responsive design completo

## Differenze dalla UI Attuale

### Attuale (app/ui.py)
- Ricerca testuale libera con filtri tecnici (speed, freehub, brake, etc.)
- Risultati flat in una tabella unica
- Facet filtering post-ricerca

### PN-first (Mockup)
- **Ricerca centrata su PN**: Input specifico per part numbers
- **Risultati raggruppati**: Card per ogni PN con offerte multiple
- **Confronto dealer**: Tabella dedicata per ogni part number
- **Cart multi-item**: Gestione avanzata con qty controls
- **Ottimizzatore**: Feature completamente nuova
- **Focus su dealer**: Filtri e comparazione basati su fornitori

## Stato delle Feature

### Implementato nel Mockup (Visual Design)
- ✅ Layout completo
- ✅ Design system
- ✅ Componenti UI
- ✅ Responsive breakpoints
- ✅ Accessibility basics

### Da Implementare (Backend/Logic)
- ⏳ Ricerca PN API integration
- ⏳ Batch paste modal
- ⏳ Cart state management
- ⏳ Optimizer algorithm
- ⏳ Quote generation API
- ⏳ Dealer filtering logic
- ⏳ Real-time stock updates
- ⏳ Lead time calculations

## Prossimi Passi

### Fase 1: Validazione Design
1. Review del mockup con stakeholders
2. Feedback su layout e interazioni
3. Test di usabilità con utenti target
4. Iterazioni sul design

### Fase 2: Implementazione Gradio
1. Convertire HTML mockup in componenti Gradio
2. Implementare state management per cart
3. Collegare API backend esistenti
4. Aggiungere nuove API per PN search e optimizer

### Fase 3: Testing & Refinement
1. User acceptance testing
2. Performance optimization
3. Accessibility audit completo
4. Cross-browser testing

## Design Tokens

```css
/* Colors */
--primary-blue: #2563eb
--success-green: #10b981
--warning-amber: #f59e0b
--danger-red: #ef4444
--gray-scale: #f9fafb to #111827

/* Spacing */
--space-xs: 0.25rem (4px)
--space-sm: 0.5rem (8px)
--space-md: 1rem (16px)
--space-lg: 1.5rem (24px)
--space-xl: 2rem (32px)
--space-2xl: 3rem (48px)

/* Typography */
--font-sans: System fonts stack
--font-mono: Monospace stack (for PN codes)

/* Border Radius */
--radius-sm: 0.375rem (6px)
--radius-md: 0.5rem (8px)
--radius-lg: 0.75rem (12px)

/* Shadows */
--shadow-sm: Subtle elevation
--shadow-md: Card elevation
--shadow-lg: Modal/overlay elevation
```

## Componenti Riutilizzabili

### Buttons
- `.btn` base class
- `.btn-primary` main actions
- `.btn-secondary` secondary actions
- `.btn-sm` compact size
- `.btn-full` full-width

### Cards
- `.pn-card` container
- `.pn-card-header` with title/subtitle
- `.offers-table` for dealer comparison

### Forms
- `.input-group` for labeled inputs
- `.form-group` for form fields
- `.checkbox-item` / `.radio-item` for selections

### Badges
- `.badge` base
- `.badge-success` / `.badge-danger` / `.badge-warning` semantic colors
- `.badge-best-price` special indicator

### Cart
- `.cart-card` container
- `.cart-item` individual item
- `.qty-control` quantity management
- `.cart-totals` summary section

## Note Tecniche

### Browser Support
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Android)

### CSS Features Used
- CSS Grid & Flexbox
- CSS Custom Properties (variables)
- Modern selectors (`:focus-within`, `:hover`)
- Media queries for responsive design

### Accessibilità
- Semantic HTML5
- ARIA labels (da aggiungere dove necessario)
- Keyboard navigation support
- Focus management
- Color contrast WCAG AA compliant

## Riferimenti

- **VISION.md**: Obiettivi e metriche del progetto
- **ARCH.md**: Architettura e modello dati
- **ARC-020**: Wireframe originale
- **REQ-004/005/006**: Requirements funzionali
- **TECH.md**: Stack tecnologico

---

**Versione**: 1.0
**Data**: 2025-11-12
**Stato**: Draft per review
