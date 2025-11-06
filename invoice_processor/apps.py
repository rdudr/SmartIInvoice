from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class InvoiceProcessorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'invoice_processor'
    
    def ready(self):
        """
        Initialize application components when Django starts.
        Load HSN/SAC master data into memory for analysis engine.
        """
        try:
            # Import here to avoid circular imports
            from .services.analysis_engine import load_hsn_master_data
            
            # Load HSN master data on startup
            master_data = load_hsn_master_data()
            goods_count = len(master_data.get('goods', {}))
            services_count = len(master_data.get('services', {}))
            
            logger.info(f"Invoice Processor app ready. HSN master data loaded: "
                       f"{goods_count} goods, {services_count} services")
                       
        except Exception as e:
            logger.error(f"Error initializing Invoice Processor app: {str(e)}")
            # Don't raise exception to prevent app startup failure
