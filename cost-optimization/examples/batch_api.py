#!/usr/bin/env python3
"""
Batch API Example - Save 50% on bulk tasks

The Batch API processes multiple requests asynchronously at half the cost.
Results are available within 24 hours (usually <1 hour).
"""

import os
import time
from dotenv import load_dotenv
import anthropic

load_dotenv()


class BatchProcessor:
    """Process multiple requests using the Batch API for 50% savings."""
    
    def __init__(self):
        self.client = anthropic.Anthropic()
    
    def create_batch(self, prompts: list[str], model: str = "claude-sonnet-4-5-20250514") -> str:
        """
        Create a batch job with multiple prompts.
        
        Args:
            prompts: List of prompts to process
            model: Claude model to use
            
        Returns:
            Batch ID for tracking
        """
        requests = [
            {
                "custom_id": f"task-{i:04d}",
                "params": {
                    "model": model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}]
                }
            }
            for i, prompt in enumerate(prompts)
        ]
        
        batch = self.client.messages.batches.create(requests=requests)
        return batch.id
    
    def check_status(self, batch_id: str) -> dict:
        """Check the status of a batch job."""
        batch = self.client.messages.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "status": batch.processing_status,
            "created_at": batch.created_at,
            "request_counts": batch.request_counts
        }
    
    def wait_for_completion(self, batch_id: str, poll_interval: int = 30) -> bool:
        """
        Wait for a batch to complete, polling periodically.
        
        Args:
            batch_id: The batch job ID
            poll_interval: Seconds between status checks
            
        Returns:
            True if completed successfully
        """
        print(f"Waiting for batch {batch_id} to complete...")
        
        while True:
            status = self.check_status(batch_id)
            print(f"  Status: {status['status']}, Counts: {status['request_counts']}")
            
            if status["status"] == "ended":
                return True
            elif status["status"] in ["canceled", "expired"]:
                return False
            
            time.sleep(poll_interval)
    
    def get_results(self, batch_id: str) -> list[dict]:
        """
        Retrieve results from a completed batch.
        
        Args:
            batch_id: The batch job ID
            
        Returns:
            List of results with custom_id and response
        """
        results = []
        for result in self.client.messages.batches.results(batch_id):
            if result.result.type == "succeeded":
                results.append({
                    "custom_id": result.custom_id,
                    "content": result.result.message.content[0].text,
                    "usage": {
                        "input_tokens": result.result.message.usage.input_tokens,
                        "output_tokens": result.result.message.usage.output_tokens
                    }
                })
            else:
                results.append({
                    "custom_id": result.custom_id,
                    "error": str(result.result)
                })
        return results
    
    def process_batch(self, prompts: list[str], wait: bool = True) -> list[dict]:
        """
        Convenience method to create batch and optionally wait for results.
        
        Args:
            prompts: List of prompts to process
            wait: Whether to wait for completion
            
        Returns:
            List of results if wait=True, else batch_id info
        """
        batch_id = self.create_batch(prompts)
        
        if wait:
            if self.wait_for_completion(batch_id):
                return self.get_results(batch_id)
            else:
                return [{"error": "Batch did not complete successfully"}]
        
        return [{"batch_id": batch_id, "message": "Batch created, poll for results"}]


def example_translations():
    """Example: Batch translate multiple texts."""
    print("\n" + "=" * 50)
    print("Example: Batch Translation (50% Off)")
    print("=" * 50)
    
    processor = BatchProcessor()
    
    texts = [
        "Translate to Japanese: The quick brown fox",
        "Translate to Japanese: Hello, nice to meet you",
        "Translate to Japanese: Thank you for your help",
        "Translate to Japanese: Goodbye, see you tomorrow",
        "Translate to Japanese: How is the weather today?"
    ]
    
    print(f"\nCreating batch with {len(texts)} translations...")
    batch_id = processor.create_batch(texts)
    print(f"Batch ID: {batch_id}")
    print("\nNote: Batch jobs complete within 24 hours (usually <1 hour)")
    print("Check status with: processor.check_status(batch_id)")


def example_cost_calculation():
    """Show cost comparison: Normal vs Batch API."""
    print("\n" + "=" * 50)
    print("Cost Comparison: Normal vs Batch API")
    print("=" * 50)
    
    # Pricing (Claude Sonnet 4.5, per million tokens)
    normal_input = 3.0
    normal_output = 15.0
    batch_input = 1.5  # 50% off
    batch_output = 7.5  # 50% off
    
    # Example: 100 requests, each 500 input tokens, 1000 output tokens
    num_requests = 100
    input_tokens = 500
    output_tokens = 1000
    
    total_input = num_requests * input_tokens / 1_000_000
    total_output = num_requests * output_tokens / 1_000_000
    
    normal_cost = (total_input * normal_input) + (total_output * normal_output)
    batch_cost = (total_input * batch_input) + (total_output * batch_output)
    
    print(f"\nScenario: {num_requests} requests")
    print(f"  - {input_tokens} input tokens each")
    print(f"  - {output_tokens} output tokens each")
    print(f"\n💰 Normal API cost:  ${normal_cost:.4f}")
    print(f"💰 Batch API cost:   ${batch_cost:.4f}")
    print(f"💰 Savings:          ${normal_cost - batch_cost:.4f} ({50}%)")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        exit(1)
    
    example_translations()
    example_cost_calculation()
