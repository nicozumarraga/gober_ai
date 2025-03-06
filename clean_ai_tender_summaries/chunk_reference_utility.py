import re
import json
import os
import logging
from typing import List, Dict, Any, Optional, Tuple

class ChunkReferenceUtility:
    """
    Utility for handling chunk references in AI-generated documents.
    Helps with extracting, mapping, and formatting references.
    """

    # Pattern to match chunk references like [chunk_id: chunk_0_1_caracteristicas_del_contrato]
    CHUNK_REF_PATTERN = re.compile(r'\[chunk_id:\s*([^\]]+)\]')

    def __init__(self, logger=None):
        """Initialize the chunk reference utility"""
        self.logger = logger or logging.getLogger(__name__)

    def extract_chunk_references(self, text: str) -> List[str]:
        """
        Extract all chunk references from a text

        Args:
            text: Text to extract references from

        Returns:
            List of chunk IDs referenced in the text
        """
        references = []
        matches = self.CHUNK_REF_PATTERN.findall(text)
        for match in matches:
            chunk_id = match.strip()
            references.append(chunk_id)
        return references

    def load_chunk_metadata(self, chunks_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Load chunk metadata from a chunks JSON file

        Args:
            chunks_path: Path to the chunks JSON file

        Returns:
            Dictionary mapping chunk IDs to their metadata
        """
        try:
            with open(chunks_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)

            # Create a mapping of chunk IDs to metadata
            chunk_metadata = {}
            for chunk in chunks:
                chunk_id = chunk['metadata']['chunk_id']
                chunk_metadata[chunk_id] = chunk['metadata']

            return chunk_metadata

        except Exception as e:
            self.logger.error(f"Error loading chunk metadata from {chunks_path}: {e}")
            return {}

    def replace_references_with_links(
        self,
        text: str,
        chunk_metadata: Dict[str, Dict[str, Any]],
        link_format: str = '<a href="pdf_path#page=page_number" class="chunk-reference" data-chunk-id="chunk_id">📄</a>'
    ) -> str:
        """
        Replace chunk references in text with links to the original PDFs

        Args:
            text: Text containing chunk references
            chunk_metadata: Mapping of chunk IDs to metadata
            link_format: Format string for the link

        Returns:
            Text with references replaced with links
        """
        def replace_reference(match):
            chunk_id = match.group(1).strip()

            # Try exact match first
            if chunk_id in chunk_metadata:
                metadata = chunk_metadata[chunk_id]
                pdf_path = metadata.get('pdf_path', '')
                page_number = metadata.get('page_number', 1)

                # Create a link to the PDF
                link = link_format.replace('pdf_path', pdf_path)
                link = link.replace('page_number', str(page_number))
                link = link.replace('chunk_id', chunk_id)

                # Return the link with the original reference
                return link

            # If exact match fails, try fuzzy matching based on chunk ID components
            if '_' in chunk_id:
                # Parse components of the chunk ID (e.g., chunk_4_2_título)
                components = chunk_id.split('_')
                if len(components) >= 3:
                    # Extract the numerical part (e.g., 4_2)
                    chunk_prefix = '_'.join(components[:3])

                    # Find candidates with matching prefix
                    candidates = []
                    for existing_id in chunk_metadata.keys():
                        if existing_id.startswith(chunk_prefix):
                            candidates.append(existing_id)

                    # If we found candidates, use the first one
                    if candidates:
                        best_match = candidates[0]
                        self.logger.info(f"Fuzzy matched chunk ID '{chunk_id}' to '{best_match}'")

                        metadata = chunk_metadata[best_match]
                        pdf_path = metadata.get('pdf_path', '')
                        page_number = metadata.get('page_number', 1)

                        # Create a link to the PDF
                        link = link_format.replace('pdf_path', pdf_path)
                        link = link.replace('page_number', str(page_number))
                        link = link.replace('chunk_id', best_match)  # Use the matched ID for data attribute

                        # Return the link with the original reference
                        return link

            # If chunk not found, leave the reference intact and log the missing reference
            self.logger.warning(f"Chunk reference not found: {chunk_id}")
            return match.group(0)

        # Replace all references
        return self.CHUNK_REF_PATTERN.sub(replace_reference, text)

    def process_document_with_references(
        self,
        document_path: str,
        chunks_path: str,
        output_path: Optional[str] = None,
        link_format: str = '<a href="pdf_path#page=page_number" class="chunk-reference" data-chunk-id="chunk_id">📄</a>'
    ) -> str:
        """
        Process a document by replacing chunk references with links

        Args:
            document_path: Path to the document with references
            chunks_path: Path to the chunks JSON file
            output_path: Path to save the processed document
            link_format: Format string for links

        Returns:
            Processed document text
        """
        try:
            # Load document
            with open(document_path, 'r', encoding='utf-8') as f:
                document_text = f.read()

            # Extract all chunk references for statistics
            chunk_ids = self.extract_chunk_references(document_text)
            self.logger.info(f"Found {len(chunk_ids)} chunk references in the document")

            # Load chunk metadata
            chunk_metadata = self.load_chunk_metadata(chunks_path)

            if not chunk_metadata:
                self.logger.warning(f"No chunk metadata found in {chunks_path}")
                return document_text

            # Count exact vs. fuzzy matches for reporting
            exact_matches = 0
            fuzzy_matches = 0
            no_matches = 0

            for chunk_id in chunk_ids:
                if chunk_id in chunk_metadata:
                    exact_matches += 1
                else:
                    # Check if fuzzy matching would work
                    if '_' in chunk_id:
                        components = chunk_id.split('_')
                        if len(components) >= 3:
                            chunk_prefix = '_'.join(components[:3])
                            for existing_id in chunk_metadata.keys():
                                if existing_id.startswith(chunk_prefix):
                                    fuzzy_matches += 1
                                    break
                            else:
                                no_matches += 1
                        else:
                            no_matches += 1
                    else:
                        no_matches += 1

            # Log statistics
            total = exact_matches + fuzzy_matches + no_matches
            self.logger.info(f"Reference statistics: {exact_matches} exact matches ({exact_matches/total:.1%}), "
                            f"{fuzzy_matches} fuzzy matches ({fuzzy_matches/total:.1%}), "
                            f"{no_matches} no matches ({no_matches/total:.1%})")

            # Replace references with links
            processed_text = self.replace_references_with_links(document_text, chunk_metadata, link_format)

            # Save processed document if output path is provided
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(processed_text)
                self.logger.info(f"Processed document saved to {output_path}")

            return processed_text

        except Exception as e:
            self.logger.error(f"Error processing document: {e}")
            return ""

    def generate_reference_metadata(
        self,
        document_path: str,
        chunks_path: str,
        output_path: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate reference metadata for a document

        Args:
            document_path: Path to the document with references
            chunks_path: Path to the chunks JSON file
            output_path: Path to save the reference metadata

        Returns:
            Dictionary with reference metadata
        """
        try:
            # Load document
            with open(document_path, 'r', encoding='utf-8') as f:
                document_text = f.read()

            # Extract all chunk references
            chunk_ids = self.extract_chunk_references(document_text)

            # Load chunk metadata
            chunk_metadata = self.load_chunk_metadata(chunks_path)

            # Create reference metadata
            reference_metadata = {
                "document_path": document_path,
                "references": []
            }

            # Add information for each referenced chunk
            for chunk_id in chunk_ids:
                metadata = None
                matched_id = chunk_id

                # Try exact match first
                if chunk_id in chunk_metadata:
                    metadata = chunk_metadata[chunk_id]
                # If exact match fails, try fuzzy matching based on chunk ID components
                elif '_' in chunk_id:
                    # Parse components of the chunk ID (e.g., chunk_4_2_título)
                    components = chunk_id.split('_')
                    if len(components) >= 3:
                        # Extract the numerical part (e.g., 4_2)
                        chunk_prefix = '_'.join(components[:3])

                        # Find candidates with matching prefix
                        candidates = []
                        for existing_id in chunk_metadata.keys():
                            if existing_id.startswith(chunk_prefix):
                                candidates.append(existing_id)

                        # If we found candidates, use the first one
                        if candidates:
                            matched_id = candidates[0]
                            metadata = chunk_metadata[matched_id]
                            self.logger.info(f"Fuzzy matched chunk ID '{chunk_id}' to '{matched_id}' for metadata")

                if metadata:
                    reference_metadata["references"].append({
                        "chunk_id": chunk_id,
                        "matched_id": matched_id,
                        "pdf_path": metadata.get('pdf_path', ''),
                        "page_number": metadata.get('page_number', 1),
                        "title": metadata.get('title', ''),
                        "level": metadata.get('level', 0)
                    })
                else:
                    self.logger.warning(f"Chunk {chunk_id} not found in metadata")

            # Save reference metadata if output path is provided
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(reference_metadata, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Reference metadata saved to {output_path}")

            return reference_metadata

        except Exception as e:
            self.logger.error(f"Error generating reference metadata: {e}")
            return {"document_path": document_path, "references": []}
