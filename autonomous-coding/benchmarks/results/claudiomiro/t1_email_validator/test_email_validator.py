"""Tests for email_validator module."""

from email_validator import validate_email


class TestValidEmails:
    """Tests for emails that should be valid."""

    def test_simple_email(self):
        """Test basic email format."""
        assert validate_email("user@example.com") is True

    def test_dotted_local_and_domain(self):
        """Test email with dots in local and domain parts."""
        assert validate_email("user.name@domain.co.uk") is True

    def test_plus_in_local(self):
        """Test email with plus sign in local part."""
        assert validate_email("user+tag@example.org") is True


class TestInvalidEmails:
    """Tests for emails that should be invalid."""

    # Structural issues
    def test_no_local_part(self):
        """Test email with no local part."""
        assert validate_email("@example.com") is False

    def test_no_domain(self):
        """Test email with no domain."""
        assert validate_email("user@") is False

    def test_double_at(self):
        """Test email with multiple @ symbols."""
        assert validate_email("user@@example.com") is False

    def test_no_at_symbol(self):
        """Test email with no @ symbol."""
        assert validate_email("userexample.com") is False

    def test_empty_string(self):
        """Test empty string."""
        assert validate_email("") is False

    # Dot issues
    def test_leading_dot_in_domain(self):
        """Test email with leading dot in domain."""
        assert validate_email("user@.com") is False

    def test_consecutive_dots_in_domain(self):
        """Test email with consecutive dots in domain."""
        assert validate_email("user@example..com") is False

    def test_leading_dot_in_local(self):
        """Test email with leading dot in local part."""
        assert validate_email(".user@example.com") is False

    def test_trailing_dot_in_local(self):
        """Test email with trailing dot in local part."""
        assert validate_email("user.@example.com") is False

    def test_trailing_dot_in_domain(self):
        """Test email with trailing dot in domain."""
        assert validate_email("user@example.com.") is False

    def test_consecutive_dots_in_local(self):
        """Test email with consecutive dots in local part."""
        assert validate_email("user..name@example.com") is False

    # Length issues
    def test_local_too_long(self):
        """Test email with local part exceeding 64 characters."""
        long_local = "a" * 65 + "@example.com"
        assert validate_email(long_local) is False

    def test_domain_too_long(self):
        """Test email with domain exceeding 255 characters."""
        long_domain = "user@" + "a" * 252 + ".com"
        assert validate_email(long_domain) is False

    # Character issues
    def test_space_in_local(self):
        """Test email with space in local part."""
        assert validate_email("user name@example.com") is False

    def test_space_in_domain(self):
        """Test email with space in domain."""
        assert validate_email("user@exam ple.com") is False

    def test_disallowed_char_in_local(self):
        """Test email with disallowed character in local part."""
        assert validate_email("user!@example.com") is False

    def test_disallowed_char_in_domain(self):
        """Test email with disallowed character in domain."""
        assert validate_email("user@example#.com") is False

    # Domain structure
    def test_no_dot_in_domain(self):
        """Test email with no dot in domain."""
        assert validate_email("user@example") is False
