from odoo import models


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    """Extend base partner merge wizard to handle customer cleanup merges"""
    
    _inherit = 'base.partner.merge.automatic.wizard'

    def _update_values(self, src_partners, dst_partner):
        """Override to prevent field value merging during customer cleanup
        
        When called from customer merge cleanup (with customer_merge_cleanup context),
        skip the field value copying to preserve the general partner's original data.
        For normal manual merges, use the standard behavior.
        """
        if self.env.context.get('customer_merge_cleanup'):
            # Skip field value updates for customer cleanup merges
            # Only foreign keys and references will be updated, preserving dst_partner's values
            return
        
        # Use standard merge behavior for normal merges
        return super()._update_values(src_partners, dst_partner)