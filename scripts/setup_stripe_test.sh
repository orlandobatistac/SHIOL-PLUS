#!/bin/bash
# Quick setup script for Stripe payment verification testing

echo "=============================================="
echo "Stripe Payment Fix - Quick Setup"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Stripe keys are set
echo "Checking environment variables..."
echo ""

if [ -z "$STRIPE_SECRET_KEY" ]; then
    echo -e "${YELLOW}⚠️  STRIPE_SECRET_KEY not set${NC}"
    echo "   Set it with: export STRIPE_SECRET_KEY='sk_test_...'"
    MISSING_VARS=true
else
    echo -e "${GREEN}✅ STRIPE_SECRET_KEY is set${NC}"
fi

if [ -z "$STRIPE_WEBHOOK_SECRET" ]; then
    echo -e "${YELLOW}⚠️  STRIPE_WEBHOOK_SECRET not set (optional for test mode)${NC}"
    echo "   Set it with: export STRIPE_WEBHOOK_SECRET='whsec_test_...'"
else
    echo -e "${GREEN}✅ STRIPE_WEBHOOK_SECRET is set${NC}"
fi

if [ -z "$STRIPE_PRICE_ID_ANNUAL" ]; then
    echo -e "${YELLOW}⚠️  STRIPE_PRICE_ID_ANNUAL not set${NC}"
    echo "   Set it with: export STRIPE_PRICE_ID_ANNUAL='price_test_...'"
    MISSING_VARS=true
else
    echo -e "${GREEN}✅ STRIPE_PRICE_ID_ANNUAL is set${NC}"
fi

if [ -z "$FEATURE_BILLING_ENABLED" ]; then
    echo -e "${YELLOW}⚠️  FEATURE_BILLING_ENABLED not set, enabling by default${NC}"
    export FEATURE_BILLING_ENABLED="true"
else
    echo -e "${GREEN}✅ FEATURE_BILLING_ENABLED is set${NC}"
fi

echo ""
echo "=============================================="
echo "Running Tests"
echo "=============================================="
echo ""

# Run the test suite
if [ -f "tests/test_payment_flow.py" ]; then
    echo "Running payment flow test suite..."
    python tests/test_payment_flow.py
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ All tests passed!${NC}"
        echo ""
        echo "=============================================="
        echo "Next Steps"
        echo "=============================================="
        echo ""
        echo "1. Start the application:"
        echo "   python main.py"
        echo ""
        echo "2. Open browser to: http://localhost:8000"
        echo ""
        echo "3. Click 'Upgrade to Premium'"
        echo ""
        echo "4. Use test card: 4242 4242 4242 4242"
        echo ""
        echo "5. Expected: Success in 2-6 seconds ✅"
        echo ""
        echo "=============================================="
        echo "Optional: Webhook Testing"
        echo "=============================================="
        echo ""
        echo "To test with webhooks (optional):"
        echo ""
        echo "1. Install Stripe CLI:"
        echo "   brew install stripe/stripe-cli/stripe"
        echo ""
        echo "2. Forward webhooks:"
        echo "   stripe listen --forward-to localhost:8000/api/v1/billing/webhook"
        echo ""
        echo "3. Copy webhook secret and set:"
        echo "   export STRIPE_WEBHOOK_SECRET='whsec_...'"
        echo ""
        echo "4. Restart application and test"
        echo ""
        echo "=============================================="
        echo "Documentation"
        echo "=============================================="
        echo ""
        echo "📄 Full docs: docs/STRIPE_PAYMENT_FIX.md"
        echo "📝 Quick ref: docs/STRIPE_PAYMENT_FIX_QUICK_REF.md"
        echo "📊 Summary: STRIPE_PAYMENT_FIX_SUMMARY.md"
        echo "🎨 Diagrams: docs/STRIPE_PAYMENT_FLOW_DIAGRAMS.md"
        echo ""
    else
        echo ""
        echo -e "${RED}❌ Some tests failed${NC}"
        echo ""
        echo "Please check the error messages above."
        echo "Common issues:"
        echo "  - Database not initialized"
        echo "  - Missing dependencies"
        echo "  - File permissions"
        echo ""
    fi
else
    echo -e "${RED}❌ Test script not found: tests/test_payment_flow.py${NC}"
    echo ""
fi

if [ "$MISSING_VARS" = true ]; then
    echo ""
    echo -e "${YELLOW}=============================================="
    echo "⚠️  WARNING: Missing Required Variables"
    echo "=============================================="
    echo ""
    echo "The fix will work in test mode without webhooks,"
    echo "but you need to set these for full testing:"
    echo ""
    echo "export STRIPE_SECRET_KEY='sk_test_...'"
    echo "export STRIPE_PRICE_ID_ANNUAL='price_test_...'"
    echo ""
    echo "Get these from: https://dashboard.stripe.com/test/apikeys"
    echo -e "${NC}"
fi
