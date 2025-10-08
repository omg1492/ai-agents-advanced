"""Test HTML sanitizer security validation."""
import pytest
from main import sanitize_html, HTMLSanitizerError


def test_sanitizer_blocks_iframe():
    """Test that forbidden tags like iframe are rejected."""
    html = '<html><body><iframe src="evil.com"></iframe></body></html>'
    
    with pytest.raises(HTMLSanitizerError, match="Forbidden tag detected: <iframe>"):
        sanitize_html(html)


def test_sanitizer_blocks_external_script():
    """Test that external scripts are rejected."""
    html = '<html><body><script src="https://evil.com/bad.js"></script></body></html>'
    
    with pytest.raises(HTMLSanitizerError, match="External script tag detected"):
        sanitize_html(html)


def test_sanitizer_blocks_external_stylesheet():
    """Test that external stylesheets are rejected (link tag not whitelisted)."""
    html = '<html><head><link rel="stylesheet" href="https://evil.com/bad.css"></head></html>'
    
    # Link tag is not in the whitelist, so it will be removed during sanitization
    result = sanitize_html(html)
    
    # Should not contain link tag
    assert "<link" not in result


def test_sanitizer_blocks_javascript_protocol():
    """Test that javascript: protocol in href is rejected."""
    html = '<html><body><a href="javascript:alert(1)">Click</a></body></html>'
    
    with pytest.raises(HTMLSanitizerError, match="Dangerous href protocol detected"):
        sanitize_html(html)


def test_sanitizer_blocks_data_uri_script():
    """Test that scripts with any src (including data URIs) are rejected."""
    html = '<html><body><script src="data:text/javascript,alert(1)"></script></body></html>'
    
    # Script tags with src attribute are blocked before data URI validation
    with pytest.raises(HTMLSanitizerError, match="External script tag detected"):
        sanitize_html(html)


def test_sanitizer_removes_event_handlers():
    """Test that dangerous event handler attributes are removed."""
    html = '<html><body><button onclick="alert(1)" onmouseover="alert(2)">Click</button></body></html>'
    
    result = sanitize_html(html)
    
    # Should not contain event handlers
    assert "onclick" not in result
    assert "onmouseover" not in result
    # But should still have the button
    assert "<button>" in result


def test_sanitizer_removes_comments():
    """Test that HTML comments are removed."""
    html = '<html><body><!-- malicious comment --><p>Hello</p></body></html>'
    
    result = sanitize_html(html)
    
    # Should not contain comments
    assert "<!--" not in result
    assert "malicious comment" not in result
    # But should have the paragraph
    assert "<p>Hello</p>" in result


def test_sanitizer_removes_non_whitelisted_tags():
    """Test that non-whitelisted tags are removed."""
    html = '<html><body><blink>Old school</blink><p>Modern</p></body></html>'
    
    result = sanitize_html(html)
    
    # Should not contain blink tag
    assert "<blink>" not in result
    # But should have the paragraph
    assert "<p>Modern</p>" in result


def test_sanitizer_allows_safe_html():
    """Test that safe, self-contained HTML is allowed."""
    html = '''<!DOCTYPE html>
<html>
<head>
    <style>
        body { background: #f0f0f0; }
        .card { padding: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Hello World</h1>
        <p>This is safe HTML.</p>
        <button>Click Me</button>
    </div>
    <script>
        document.querySelector('button').addEventListener('click', () => {
            alert('Safe inline script');
        });
    </script>
</body>
</html>'''
    
    result = sanitize_html(html)
    
    # Should preserve structure
    assert "<!DOCTYPE html>" in result
    assert "<style>" in result
    assert "<script>" in result
    assert "<button>" in result
    assert "Hello World" in result


def test_sanitizer_allows_data_uri_for_images():
    """Test that data: URIs are allowed for images."""
    html = '<html><body><img src="data:image/png;base64,iVBORw0KG..." alt="test"></body></html>'
    
    # Should not raise an error
    result = sanitize_html(html)
    
    assert "<img" in result
    assert "data:image/png" in result


def test_sanitizer_warns_about_dangerous_js():
    """Test that dangerous JS patterns generate warnings but don't reject."""
    html = '''<html><body>
<script>
    // This would be warned about but not rejected
    setTimeout(function() { console.log('test'); }, 1000);
</script>
</body></html>'''
    
    # Should still sanitize (with warnings logged)
    result = sanitize_html(html)
    
    assert "<script>" in result
    assert "setTimeout" in result


def test_sanitizer_rejects_empty_html():
    """Test that empty HTML is rejected."""
    with pytest.raises(HTMLSanitizerError, match="HTML cannot be empty"):
        sanitize_html("")
    
    with pytest.raises(HTMLSanitizerError, match="HTML cannot be empty"):
        sanitize_html("   ")


def test_sanitizer_extended_event_handlers():
    """Test that extended list of event handlers are removed."""
    html = '''<html><body>
        <div ondrag="alert(1)" ondrop="alert(2)" onscroll="alert(3)" 
             onwheel="alert(4)" oncopy="alert(5)">Test</div>
    </body></html>'''
    
    result = sanitize_html(html)
    
    # Should not contain any of these handlers
    assert "ondrag" not in result
    assert "ondrop" not in result
    assert "onscroll" not in result
    assert "onwheel" not in result
    assert "oncopy" not in result
