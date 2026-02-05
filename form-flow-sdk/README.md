# FormFlow Plugin SDK

Voice-driven data collection widget for external applications.

## Quick Start

### Script Tag Integration (Simplest)

Add this single script tag to your HTML:

```html
<script 
  src="https://cdn.formflow.io/plugin-sdk.min.js"
  data-api-key="YOUR_API_KEY"
  data-plugin-id="YOUR_PLUGIN_ID">
</script>
```

The widget will appear automatically in the bottom-right corner.

### Script Tag Options

| Attribute | Description | Required |
|-----------|-------------|----------|
| `data-api-key` | Your plugin API key | Yes |
| `data-plugin-id` | Your plugin ID | Yes |
| `data-container` | CSS selector for custom container | No |
| `data-language` | Voice recognition language (default: en-US) | No |
| `data-title` | Widget title | No |
| `data-subtitle` | Widget subtitle | No |

---

## Programmatic Integration

### JavaScript

```html
<div id="my-widget"></div>

<script src="https://cdn.formflow.io/plugin-sdk.min.js"></script>
<script>
  FormFlowPlugin.init({
    apiKey: 'YOUR_API_KEY',
    pluginId: 'YOUR_PLUGIN_ID',
    container: '#my-widget',
    language: 'en-US',
    title: 'Voice Assistant',
    subtitle: 'Tap to speak',
    
    onStart: function(session) {
      console.log('Session started:', session.session_id);
    },
    
    onProgress: function(data) {
      console.log('Progress:', data.progress + '%');
    },
    
    onComplete: function(result) {
      console.log('Complete!', result.extracted_values);
    },
    
    onError: function(error) {
      console.error('Error:', error.message);
    }
  });
</script>
```

---

## React Integration

### Installation

```bash
npm install @formflow/plugin-sdk
```

### Usage

```tsx
import { FormFlowWidget } from '@formflow/plugin-sdk/react';

function App() {
  return (
    <FormFlowWidget
      apiKey="YOUR_API_KEY"
      pluginId="YOUR_PLUGIN_ID"
      title="Voice Assistant"
      onComplete={(result) => {
        console.log('Data collected:', result.extracted_values);
      }}
    />
  );
}
```

### Props

| Prop | Type | Description |
|------|------|-------------|
| `apiKey` | `string` | Plugin API key (required) |
| `pluginId` | `string` | Plugin ID (required) |
| `apiBase` | `string` | Custom API URL |
| `title` | `string` | Widget title |
| `subtitle` | `string` | Widget subtitle |
| `language` | `string` | Voice language (default: en-US) |
| `onStart` | `function` | Session start callback |
| `onComplete` | `function` | Completion callback |
| `onError` | `function` | Error callback |
| `onProgress` | `function` | Progress callback |
| `className` | `string` | Custom CSS class |
| `style` | `object` | Inline styles |

### Hook for Advanced Control

```tsx
import { useFormFlowPlugin } from '@formflow/plugin-sdk/react';

function MyComponent() {
  const { isReady, init, destroy } = useFormFlowPlugin({
    apiKey: 'YOUR_API_KEY',
    pluginId: 'YOUR_PLUGIN_ID'
  });

  useEffect(() => {
    if (isReady) {
      init('#custom-container');
    }
    return () => destroy();
  }, [isReady]);

  return <div id="custom-container" />;
}
```

---

## Advanced Usage

### Custom Widget Styling

```html
<style>
  .formflow-widget {
    --ff-primary: #4F46E5;
    --ff-success: #10b981;
    --ff-error: #dc2626;
    --ff-radius: 16px;
  }
</style>
```

### Direct API Access

```javascript
const client = new FormFlowPlugin.APIClient({
  apiKey: 'YOUR_API_KEY',
  pluginId: 'YOUR_PLUGIN_ID'
});

// Start session
const session = await client.startSession({ source: 'custom' });

// Submit text input directly
const response = await client.submitInput(
  session.session_id,
  'My name is John and my email is john@example.com',
  'request_123'
);

// Complete and trigger database insert
const result = await client.completeSession(session.session_id);
```

### Voice-Only (No Widget)

```javascript
const recognizer = new FormFlowPlugin.VoiceRecognizer(
  (transcript, isFinal) => {
    console.log(isFinal ? 'Final:' : 'Interim:', transcript);
  },
  (error) => {
    console.error('Voice error:', error);
  },
  { language: 'en-US' }
);

recognizer.start();
// ... later
recognizer.stop();
```

---

## Events & Callbacks

### Session Lifecycle

1. **onStart(session)** - Called when session begins
   ```js
   { session_id: 'abc123', current_question: 'What is your name?' }
   ```

2. **onProgress(data)** - Called after each successful input
   ```js
   { 
     progress: 50, 
     completed_fields: ['name'], 
     remaining_fields: ['email'],
     next_question: 'What is your email?'
   }
   ```

3. **onComplete(result)** - Called when all data collected
   ```js
   {
     session_id: 'abc123',
     extracted_values: { name: 'John', email: 'john@example.com' },
     inserted_rows: 1,
     status: 'success'
   }
   ```

4. **onError(error)** - Called on any error
   ```js
   { message: 'Network error', code: 'NETWORK_ERROR' }
   ```

---

## Supported Languages

Voice recognition supports:
- `en-US` - English (US)
- `en-GB` - English (UK)
- `en-IN` - English (India)
- `es-ES` - Spanish
- `fr-FR` - French
- `de-DE` - German
- `hi-IN` - Hindi
- `ja-JP` - Japanese
- `zh-CN` - Chinese (Simplified)

---

## Security

- All API calls require valid API key
- HMAC-signed webhooks for server notifications
- HTTPS required for voice recognition
- Rate limiting applied per API key

---

## Browser Support

| Browser | Voice Support |
|---------|--------------|
| Chrome 33+ | ✅ Full |
| Edge 79+ | ✅ Full |
| Safari 14.1+ | ✅ Full |
| Firefox | ❌ No (text-only fallback) |

---

## Troubleshooting

### Widget not appearing
- Check browser console for errors
- Verify API key and plugin ID
- Ensure script loads before DOM ready

### Voice not working
- HTTPS required (localhost exempt)
- Grant microphone permission
- Check browser compatibility

### Data not saving
- Verify plugin database connection
- Check webhook logs for errors
- Confirm field mappings match

---

## Support

- Documentation: https://docs.formflow.io/plugins
- Issues: https://github.com/formflow/plugin-sdk/issues
- Email: support@formflow.io
