'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from '@/components/theme-toggle';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { profileApi } from '@/utils/api';
import { AdminChatHistory } from '@/components/admin/chat-history';
import { useAuth } from '@/hooks/useAuth';
import type { ProfileData } from '@/utils/types';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { redirect } from 'next/navigation';
import { ProjectManagement } from '@/components/admin/project-management';

export default function AdminPage() {
  const [formData, setFormData] = useState<ProfileData>({
    bio: "",
    skills: "",
    experience: "",
    projects: "",
    interests: "",
    calendly_link: "",
    meeting_rules: ""
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("profile");
  const [isEditMode, setIsEditMode] = useState(false);
  
  // Use the standardized useAuth hook
  const { user, loading, signOut } = useAuth();

  // Redirect to home if not authenticated
  useEffect(() => {
    if (!loading && !user) {
      redirect('/');
    }
  }, [user, loading]);

  // Fetch profile data when user is available
  useEffect(() => {
    if (user) {
      fetchProfileData(user.id);
    }
  }, [user]);
  
  const fetchProfileData = async (userId: string) => {
    try {
      setIsLoading(true);
      console.log(`Fetching profile data for user: ${userId}`);
      
      const data = await profileApi.getProfileData(userId);
      console.log('Received profile data:', data);
      
      // Ensure data complies with our ProfileData interface
      setFormData({
        bio: data.bio || "No bio available",
        skills: data.skills || "No skills listed",
        experience: data.experience || "No experience listed",
        interests: data.interests || "No interests listed",
        name: data.name || "",
        location: data.location || "",
        user_id: data.user_id || userId, // Preserve user_id
        calendly_link: data.calendly_link || "",
        meeting_rules: data.meeting_rules || "",
        // Don't include projects field here as it might not exist in newer schemas
      });
      
      setError(null);
    } catch (err) {
      console.error('Failed to fetch profile data:', err);
      setError('Failed to load profile data. Using default values.');
      
      // Set default values in case of error
      setFormData({
        bio: "Enter your bio here",
        skills: "Enter your skills here",
        experience: "Enter your experience here",
        interests: "Enter your interests here",
        user_id: userId, // Always include user_id even with default values
        calendly_link: "",
        meeting_rules: "",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccess(false);
    setError(null);
    
    try {
      if (!user) {
        throw new Error('You must be logged in to update your profile');
      }
      
      // Create a cleaned version of the form data without projects field
      // to avoid Supabase column issues
      const cleanedData = {
        bio: formData.bio,
        skills: formData.skills,
        experience: formData.experience,
        interests: formData.interests,
        name: formData.name,
        location: formData.location,
        user_id: user.id,
        calendly_link: formData.calendly_link,
        meeting_rules: formData.meeting_rules,
      };
      
      console.log('Submitting profile data with user_id:', user.id);
      
      // Call API to update data with the cleaned data object
      const result = await profileApi.updateProfileData(cleanedData);
      
      console.log('Profile update result:', result);
      
      setSaveSuccess(true);
      setIsEditMode(false); // Exit edit mode after successful save
      
      // Display success message and automatically clear it after 3 seconds
      setTimeout(() => {
        setSaveSuccess(false);
      }, 3000);
      
      // Refresh data from server to ensure we see the latest
      await fetchProfileData(user.id);
    } catch (err: any) {
      console.error('Error saving data:', err);
      setError(err?.message || 'Failed to save data. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRefresh = async () => {
    if (user) {
      await fetchProfileData(user.id);
    }
  };

  // Show loading state while authenticating
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-muted/40">
        <Card className="w-full max-w-md">
          <CardContent className="flex flex-col items-center justify-center p-6">
            <p className="text-lg font-medium">Loading...</p>
            <p className="text-sm text-muted-foreground">Please wait while we authenticate you</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Show a message if not authenticated
  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-muted/40">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-2xl">Authentication Required</CardTitle>
            <CardDescription>
              You need to be signed in to access the admin panel
            </CardDescription>
          </CardHeader>
          <CardFooter className="flex justify-center">
            <Button asChild>
              <Link href="/">Back to Home</Link>
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <header className="sticky top-0 z-10 bg-background border-b py-4">
        <div className="container mx-auto px-4 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold text-primary">Personal Dashboard</h1>
            {user && (
              <p className="text-sm text-muted-foreground hidden md:block">
                Logged in as: <span className="font-medium">{user.email}</span>
              </p>
            )}
          </div>
          <nav className="flex items-center space-x-4">
            <Button variant="outline" onClick={handleRefresh} disabled={isLoading}>
              {isLoading ? 'Refreshing...' : 'Refresh Data'}
            </Button>
            <ThemeToggle />
            <Button variant="outline" asChild>
              <Link href={user ? `/chat/${user.id}` : '/'}>Back to Chatbot</Link>
            </Button>
            <Button variant="destructive" onClick={signOut}>
              Logout
            </Button>
          </nav>
        </div>
      </header>

      <main className="flex-1 container mx-auto px-4 py-6 flex flex-col">
        <Tabs 
          defaultValue="profile" 
          value={activeTab} 
          onValueChange={setActiveTab}
          className="w-full max-w-5xl mx-auto"
        >
          <div className="flex justify-center mb-8">
            <TabsList>
              <TabsTrigger value="profile">
                Profile Information
              </TabsTrigger>
              <TabsTrigger value="chat">
                Chat History
              </TabsTrigger>
              <TabsTrigger value="projects">
                Projects
              </TabsTrigger>
            </TabsList>
          </div>
          
          <TabsContent value="profile">
            <Card className="shadow-md">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-2xl font-semibold">What the AI knows about you</CardTitle>
                  {!isEditMode && !isLoading && (
                    <Button
                      onClick={() => setIsEditMode(true)}
                      variant="outline"
                      className="px-6"
                    >
                      Edit Profile
                    </Button>
                  )}
                </div>
              </CardHeader>
              
              <CardContent className="p-6">
                {saveSuccess && (
                  <div className="mb-6 p-4 rounded-md bg-green-50 border border-green-200 text-green-700 dark:bg-green-900/20 dark:border-green-900 dark:text-green-400">
                    <p className="font-medium">Success!</p>
                    <p className="text-sm">Content updated successfully and saved to database.</p>
                  </div>
                )}
                
                {error && (
                  <div className="mb-6 p-4 rounded-md bg-red-50 border border-red-200 text-red-700 dark:bg-red-900/20 dark:border-red-900 dark:text-red-400">
                    <p className="font-medium">Error</p>
                    <p className="text-sm">{error}</p>
                    <div className="mt-2">
                      <Button variant="outline" size="sm" onClick={handleRefresh}>
                        Try Again
                      </Button>
                    </div>
                  </div>
                )}
                
                {isLoading ? (
                  <div className="py-8 text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
                    <p>Loading profile data...</p>
                  </div>
                ) : isEditMode ? (
                  <form onSubmit={handleSubmit} className="space-y-8">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div className="space-y-2">
                        <Label htmlFor="name" className="text-base font-medium">Name</Label>
                        <Input
                          id="name"
                          name="name"
                          value={formData.name || ''}
                          onChange={handleChange}
                          placeholder="Your name"
                          className="text-base"
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <Label htmlFor="location" className="text-base font-medium">Location</Label>
                        <Input
                          id="location"
                          name="location"
                          value={formData.location || ''}
                          onChange={handleChange}
                          placeholder="Your location"
                          className="text-base"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center">
                        <label className="text-base font-medium">Bio</label>
                        <Badge variant="outline" className="ml-2 text-xs">Personal</Badge>
                      </div>
                      <Textarea
                        name="bio"
                        value={formData.bio}
                        onChange={handleChange}
                        rows={3}
                        className="resize-none text-base"
                        required
                      />
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center">
                        <label className="text-base font-medium">Skills</label>
                        <Badge variant="outline" className="ml-2 text-xs">Technical</Badge>
                      </div>
                      <Textarea
                        name="skills"
                        value={formData.skills}
                        onChange={handleChange}
                        rows={3}
                        className="resize-none text-base"
                        required
                      />
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center">
                        <label className="text-base font-medium">Experience</label>
                        <Badge variant="outline" className="ml-2 text-xs">Professional</Badge>
                      </div>
                      <Textarea
                        name="experience"
                        value={formData.experience}
                        onChange={handleChange}
                        rows={3}
                        className="resize-none text-base"
                        required
                      />
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center">
                        <label className="text-base font-medium">Interests & Hobbies</label>
                        <Badge variant="outline" className="ml-2 text-xs">Personal</Badge>
                      </div>
                      <Textarea
                        name="interests"
                        value={formData.interests}
                        onChange={handleChange}
                        rows={2}
                        className="resize-none text-base"
                        required
                      />
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center">
                        <label className="text-base font-medium">Calendly Link</label>
                        <Badge variant="outline" className="ml-2 text-xs">Meeting</Badge>
                      </div>
                      <Input
                        name="calendly_link"
                        value={formData.calendly_link || ''}
                        onChange={handleChange}
                        placeholder="Your Calendly scheduling link"
                        className="text-base"
                      />
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center">
                        <label className="text-base font-medium">Meeting Rules</label>
                        <Badge variant="outline" className="ml-2 text-xs">Policy</Badge>
                      </div>
                      <Textarea
                        name="meeting_rules"
                        value={formData.meeting_rules || ''}
                        onChange={handleChange}
                        rows={3}
                        placeholder="Define rules for when meetings should be allowed (e.g., 'Only allow meetings for project discussions, job opportunities, or consulting inquiries')"
                        className="resize-none text-base"
                      />
                    </div>
                    
                    <div className="flex justify-end gap-2 pt-6">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setIsEditMode(false)}
                        disabled={isSaving}
                        className="px-6"
                      >
                        Cancel
                      </Button>
                      <Button
                        type="submit"
                        disabled={isSaving}
                        className="px-8"
                      >
                        {isSaving ? 'Saving...' : 'Save Changes'}
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="space-y-8">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div className="space-y-2">
                        <h3 className="text-base font-semibold">Name</h3>
                        <p className="text-lg">{formData.name || 'Not specified'}</p>
                      </div>
                      
                      <div className="space-y-2">
                        <h3 className="text-base font-semibold">Location</h3>
                        <p className="text-lg">{formData.location || 'Not specified'}</p>
                      </div>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center border-b pb-2">
                        <h3 className="text-base font-semibold">Bio</h3>
                        <Badge variant="outline" className="ml-2 text-xs">Personal</Badge>
                      </div>
                      <p className="text-base leading-relaxed whitespace-pre-wrap">{formData.bio}</p>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center border-b pb-2">
                        <h3 className="text-base font-semibold">Skills</h3>
                        <Badge variant="outline" className="ml-2 text-xs">Technical</Badge>
                      </div>
                      <p className="text-base leading-relaxed whitespace-pre-wrap">{formData.skills}</p>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center border-b pb-2">
                        <h3 className="text-base font-semibold">Experience</h3>
                        <Badge variant="outline" className="ml-2 text-xs">Professional</Badge>
                      </div>
                      <p className="text-base leading-relaxed whitespace-pre-wrap">{formData.experience}</p>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center border-b pb-2">
                        <h3 className="text-base font-semibold">Interests & Hobbies</h3>
                        <Badge variant="outline" className="ml-2 text-xs">Personal</Badge>
                      </div>
                      <p className="text-base leading-relaxed whitespace-pre-wrap">{formData.interests}</p>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center border-b pb-2">
                        <h3 className="text-base font-semibold">Calendly Link</h3>
                        <Badge variant="outline" className="ml-2 text-xs">Meeting</Badge>
                      </div>
                      <p className="text-base leading-relaxed break-all">
                        {formData.calendly_link || 'No meeting link configured'}
                      </p>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center border-b pb-2">
                        <h3 className="text-base font-semibold">Meeting Rules</h3>
                        <Badge variant="outline" className="ml-2 text-xs">Policy</Badge>
                      </div>
                      <p className="text-base leading-relaxed whitespace-pre-wrap">
                        {formData.meeting_rules || 'No meeting rules configured'}
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="chat">
            <AdminChatHistory userId={user.id} />
          </TabsContent>

          <TabsContent value="projects">
            <ProjectManagement userId={user.id} />
          </TabsContent>
        </Tabs>
      </main>

      <footer className="bg-muted py-4 mt-auto">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          Agent Ciril - Interactive AI Portfolio &copy; {new Date().getFullYear()}
        </div>
      </footer>
    </div>
  );
} 